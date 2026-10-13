import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2 as httpx
from pydantic import AnyUrl

from mcp import ClientSession
from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


class JsonTokenStorage:
    def __init__(self, path: str):
        self.path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")

    async def get_tokens(self) -> OAuthToken | None:
        data = self._read().get("tokens")
        return OAuthToken.model_validate(data) if data else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._read()
        data["tokens"] = tokens.model_dump(mode="json")
        self._write(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        stored = self._read()
        data = stored.get("client_info")
        # Re-register an unauthenticated client created with the old scope.
        # Preserve any existing tokens and the stored file.
        if data and data.get("scope") == "user" and not stored.get("tokens"):
            return None
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._read()
        data["client_info"] = client_info.model_dump(mode="json")
        self._write(data)


class RobinhoodCloudMCP:
    def __init__(
        self,
        *,
        server_url: str,
        redirect_uri: str,
        storage_path: str,
    ):
        self.server_url = server_url
        self.redirect_uri = redirect_uri
        self.storage = JsonTokenStorage(storage_path)
        self.authorization_url: str | None = None
        self._callback_future: asyncio.Future[AuthorizationCodeResult] | None = None
        self.connected = False
        self.last_error: str | None = None
        self.tool_names: list[str] = []

    async def _redirect_handler(self, authorization_url: str) -> None:
        # Log only comparisons, never tokens, codes, state, or full URLs.
        try:
            stored = self.storage._read()
            info = stored.get("client_info") or {}
            query = parse_qs(urlsplit(authorization_url).query)
            registered_redirects = info.get("redirect_uris") or []
            checks = {
                "stored_client_present": bool(info.get("client_id")),
                "client_id_matches_request": bool(info.get("client_id"))
                and query.get("client_id") == [info["client_id"]],
                "configured_callback_registered": self.redirect_uri in registered_redirects,
                "request_callback_matches_config": query.get("redirect_uri") == [self.redirect_uri],
                "stored_scope_internal": info.get("scope") == "internal",
                "stored_auth_method_none": info.get("token_endpoint_auth_method") == "none",
                "stored_authorization_code_grant": "authorization_code" in (info.get("grant_types") or []),
                "stored_code_response_type": "code" in (info.get("response_types") or []),
                "tokens_present": bool(stored.get("tokens")),
            }
            print("OAUTH_REGISTRATION_CHECK " + json.dumps(checks, sort_keys=True), flush=True)
        except Exception:
            print("OAUTH_REGISTRATION_CHECK unavailable", flush=True)
        self.authorization_url = authorization_url

    async def _callback_handler(self) -> AuthorizationCodeResult:
        loop = asyncio.get_running_loop()
        self._callback_future = loop.create_future()
        return await self._callback_future

    def submit_callback(
        self,
        *,
        code: str,
        state: str | None,
        iss: str | None,
    ) -> None:
        future = self._callback_future
        if future is None or future.done():
            raise RuntimeError("No OAuth callback is currently expected.")
        future.set_result(
            AuthorizationCodeResult(
                code=code,
                state=state,
                iss=iss,
            )
        )

    def _provider(self) -> OAuthClientProvider:
        return OAuthClientProvider(
            server_url=self.server_url,
            client_metadata=OAuthClientMetadata(
                client_name="NDX Multi-Index Trading Bot",
                redirect_uris=[AnyUrl(self.redirect_uri)],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope="internal",
                token_endpoint_auth_method="none",
            ),
            storage=self.storage,
            redirect_handler=self._redirect_handler,
            callback_handler=self._callback_handler,
        )

    async def probe(self) -> None:
        self.connected = False
        self.last_error = None
        try:
            auth = self._provider()
            async with httpx.AsyncClient(
                auth=auth,
                timeout=httpx.Timeout(30.0, read=300.0),
            ) as http_client:
                async with streamable_http_client(
                    self.server_url,
                    http_client=http_client,
                ) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        self.tool_names = [tool.name for tool in tools.tools]
                        self.connected = True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        auth = self._provider()
        async with httpx.AsyncClient(
            auth=auth,
            timeout=httpx.Timeout(30.0, read=300.0),
        ) as http_client:
            async with streamable_http_client(
                self.server_url,
                http_client=http_client,
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(name, arguments)
