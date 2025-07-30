#!/usr/bin/env python3
"""
Script to apply targeted improvements to NostalgiaForInfinityX6.py more carefully
"""
import re

def apply_improvements():
    """Apply improvements with careful validation"""
    
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    print("Original file size:", len(content))
    
    if 'stoploss = -0.99' in content:
        content = content.replace('stoploss = -0.99', 'stoploss = -0.15')
        print("✅ Updated stoploss from -0.99 to -0.15")
    
    if 'use_custom_stoploss = False' in content:
        content = content.replace('use_custom_stoploss = False', 'use_custom_stoploss = True')
        print("✅ Enabled custom stoploss")
    
    if 'trailing_stop = False' in content:
        content = content.replace('trailing_stop = False', 'trailing_stop = True')
        print("✅ Enabled trailing stop")
    
    if 'return "v16.5.297"' in content:
        content = content.replace('return "v16.5.297"', 'return "v16.5.297-enhanced"')
        print("✅ Updated version number")
    
    version_method_pattern = r'(def version\(self\) -> str:\s+return "v16\.5\.297-enhanced")'
    
    if re.search(version_method_pattern, content):
        custom_stoploss_method = '''

  def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                     current_rate: float, current_profit: float, **kwargs) -> float:
    """
    Enhanced dynamic stoploss based on volatility and market conditions
    """
    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    if len(dataframe) < 1:
      return self.stoploss
      
    last_candle = dataframe.iloc[-1].squeeze()
    
    atr = last_candle.get('ATR_14', 0.02)
    volatility_multiplier = 2.0
    
    atr_stoploss = -(atr * volatility_multiplier)
    
    trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
    
    if trade_duration < 1:  # First hour - tighter stop
      dynamic_stoploss = max(atr_stoploss, -0.03)
    elif trade_duration < 6:  # First 6 hours
      dynamic_stoploss = max(atr_stoploss, -0.05)
    else:  # After 6 hours - wider stop
      dynamic_stoploss = max(atr_stoploss, -0.08)
    
    if current_profit > 0.02:  # If in profit > 2%
      dynamic_stoploss = max(dynamic_stoploss, -0.01)  # Tighter trailing
    
    return max(dynamic_stoploss, -0.15)  # Never worse than -15%'''
        
        content = re.sub(version_method_pattern, r'\1' + custom_stoploss_method, content)
        print("✅ Added custom stoploss method")
    
    btc_end_pattern = r'(# BTC informative indicators.*?)(# Indicators for normal pairs)'
    
    if re.search(btc_end_pattern, content, re.DOTALL):
        enhanced_indicators = '''
    
    df["ATR_14"] = ta.ATR(df, timeperiod=14)
    df["NATR_14"] = ta.NATR(df, timeperiod=14)
    
    df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]
    
    df["vwap"] = qtpylib.vwap(df)
    
    df["volatility_protection"] = df["NATR_14"] > df["NATR_14"].rolling(50).quantile(0.8)
    df["volume_protection"] = df["volume_ratio"] < 0.5
    df["enhanced_protection"] = df["volatility_protection"] | df["volume_protection"]
    
    '''
        
        content = re.sub(btc_end_pattern, r'\1' + enhanced_indicators + r'\2', content, flags=re.DOTALL)
        print("✅ Added enhanced indicators")
    
    print("Final file size:", len(content))
    
    with open('NostalgiaForInfinityX6.py', 'w') as f:
        f.write(content)
    
    print("✅ Targeted improvements applied successfully!")

if __name__ == "__main__":
    apply_improvements()
