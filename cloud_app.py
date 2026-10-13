import asyncio
import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from robinhood_cloud_mcp import RobinhoodCloudMCP


PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"].rstrip("/")
SETUP_KEY = os.environ["AUTH_SETUP_KEY"]
MCP_URL = os.getenv(
    "ROBINHOOD_MCP_URL",
    "https://agent.robinhood.com/mcp/trading",
)
TOKEN_PATH = os.getenv("ROBINHOOD_TOKEN_PATH", "/data/robinhood_oauth.json")

client = RobinhoodCloudMCP(
    server_url=MCP_URL,
    redirect_uri=f"{PUBLIC_BASE_URL}/oauth/callback",
    storage_path=TOKEN_PATH,
)
probe_task: asyncio.Task | None = None


async def ensure_probe() -> None:
    global probe_task
    if probe_task is None or probe_task.done():
        probe_task = asyncio.create_task(client.probe())
        await asyncio.sleep(0.25)


async def health(request: Request):
    return JSONResponse(
        {
            "ok": True,
            "robinhood_connected": client.connected,
            "oauth_ready": bool(client.authorization_url),
            "tool_count": len(client.tool_names),
            "last_error": client.last_error,
        }
    )


async def auth_start(request: Request):
    if request.query_params.get("key") != SETUP_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if client.connected:
        return JSONResponse(
            {
                "connected": True,
                "message": "Robinhood MCP is already authenticated.",
                "tool_count": len(client.tool_names),
            }
        )

    await ensure_probe()

    for _ in range(40):
        if client.authorization_url:
            return RedirectResponse(client.authorization_url, status_code=302)
        if probe_task and probe_task.done():
            try:
                probe_task.result()
            except Exception:
                pass
            if client.connected:
                return JSONResponse(
                    {
                        "connected": True,
                        "message": "Robinhood MCP authenticated from stored tokens.",
                    }
                )
            return JSONResponse(
                {
                    "connected": False,
                    "error": client.last_error or "OAuth did not start.",
                },
                status_code=503,
            )
        await asyncio.sleep(0.25)

    return JSONResponse(
        {"connected": False, "error": "Timed out waiting for OAuth URL."},
        status_code=503,
    )


async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    iss = request.query_params.get("iss")
    error = request.query_params.get("error")

    if error:
        return JSONResponse(
            {
                "connected": False,
                "error": error,
                "description": request.query_params.get("error_description"),
            },
            status_code=400,
        )

    if not code:
        return JSONResponse({"error": "Missing OAuth code."}, status_code=400)

    try:
        client.submit_callback(code=code, state=state, iss=iss)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    for _ in range(80):
        if client.connected:
            return JSONResponse(
                {
                    "connected": True,
                    "message": "Robinhood MCP authenticated successfully.",
                    "tool_count": len(client.tool_names),
                }
            )
        if probe_task and probe_task.done():
            try:
                probe_task.result()
            except Exception:
                pass
            break
        await asyncio.sleep(0.25)

    return JSONResponse(
        {
            "connected": client.connected,
            "error": client.last_error or "Authentication did not complete.",
        },
        status_code=503,
    )


async def startup():
    await ensure_probe()


routes = [
    Route("/health", health),
    Route("/auth/start", auth_start),
    Route("/oauth/callback", oauth_callback),
]

app = Starlette(routes=routes, on_startup=[startup])
