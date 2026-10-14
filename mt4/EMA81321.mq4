#property strict
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_color1 clrLimeGreen
#property indicator_color2 clrOrange
#property indicator_color3 clrDodgerBlue
#property indicator_color4 clrLimeGreen
#property indicator_color5 clrRed

// Generic chart-only indicator. Never sends orders. Uses the current chart feed.
input bool TripleAlignmentCross = true;
double Fast[], Middle[], Slow[], Bull[], Bear[];

int OnInit()
{
   SetIndexBuffer(0,Fast); SetIndexStyle(0,DRAW_LINE); SetIndexLabel(0,"EMA 8");
   SetIndexBuffer(1,Middle); SetIndexStyle(1,DRAW_LINE); SetIndexLabel(1,"EMA 13");
   SetIndexBuffer(2,Slow); SetIndexStyle(2,DRAW_LINE); SetIndexLabel(2,"EMA 21");
   SetIndexBuffer(3,Bull); SetIndexStyle(3,DRAW_ARROW); SetIndexArrow(3,233);
   SetIndexBuffer(4,Bear); SetIndexStyle(4,DRAW_ARROW); SetIndexArrow(4,234);
   SetIndexEmptyValue(3,EMPTY_VALUE); SetIndexEmptyValue(4,EMPTY_VALUE);
   ArraySetAsSeries(Fast,true); ArraySetAsSeries(Middle,true);
   ArraySetAsSeries(Slow,true); ArraySetAsSeries(Bull,true); ArraySetAsSeries(Bear,true);
   IndicatorShortName("EMA 8/13/21 closed-bar cross");
   return(INIT_SUCCEEDED);
}

int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
{
   if(rates_total<107) return(0);
   ArraySetAsSeries(high,true); ArraySetAsSeries(low,true);
   if(prev_calculated==0) { ArrayInitialize(Bull,EMPTY_VALUE); ArrayInitialize(Bear,EMPTY_VALUE); }
   int limit = prev_calculated==0 ? rates_total-1 : MathMin(rates_total-1,rates_total-prev_calculated+1);
   for(int i=limit;i>=0;i--)
   {
      Fast[i]=iMA(NULL,0,8,0,MODE_EMA,PRICE_CLOSE,i);
      Middle[i]=iMA(NULL,0,13,0,MODE_EMA,PRICE_CLOSE,i);
      Slow[i]=iMA(NULL,0,21,0,MODE_EMA,PRICE_CLOSE,i);
      Bull[i]=EMPTY_VALUE; Bear[i]=EMPTY_VALUE;
      // Shift zero is still forming: never put a crossover arrow on it.
      if(i==0 || i+106>rates_total) continue;
      double pf=iMA(NULL,0,8,0,MODE_EMA,PRICE_CLOSE,i+1);
      double pm=iMA(NULL,0,13,0,MODE_EMA,PRICE_CLOSE,i+1);
      double ps=iMA(NULL,0,21,0,MODE_EMA,PRICE_CLOSE,i+1);
      bool up=Fast[i]>Middle[i] && Middle[i]>Slow[i];
      bool down=Fast[i]<Middle[i] && Middle[i]<Slow[i];
      bool buy=TripleAlignmentCross ? up && !(pf>pm && pm>ps) : up && pf<=pm;
      bool sell=TripleAlignmentCross ? down && !(pf<pm && pm<ps) : down && pf>=pm;
      double offset=MathMax((high[i]-low[i])*0.1,10*Point);
      if(buy) Bull[i]=low[i]-offset;
      if(sell) Bear[i]=high[i]+offset;
   }
   return(rates_total);
}
