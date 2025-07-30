import copy
import logging
import math
import numpy as np
import pandas as pd
import talib.abstract as ta
import pandas_ta as pta
from pandas import DataFrame, Series
from typing import Dict, Optional, Tuple
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
    merge_informative_pair,
)
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone
import time
from functools import reduce
import warnings

warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

log = logging.getLogger(__name__)

class NostalgiaForInfinityX6_Enhanced(IStrategy):
    INTERFACE_VERSION = 3

    def version(self) -> str:
        return "v16.5.297-enhanced"

    stoploss = -0.15  # Tighter initial stoploss

    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.015

    use_custom_stoploss = True

    timeframe = "5m"
    
    informative_timeframes = ["15m", "1h", "4h", "1d"]

    max_open_trades = 6
    startup_candle_count = 800
    
    position_adjustment_enable = True
    max_entry_position_adjustment = 3
    
    volatility_lookback = IntParameter(10, 30, default=20, space="buy")
    trend_strength_threshold = DecimalParameter(0.1, 0.5, default=0.25, space="buy")
    volume_threshold = DecimalParameter(1.0, 3.0, default=1.5, space="buy")
    rsi_oversold = IntParameter(20, 35, default=30, space="buy")
    rsi_overbought = IntParameter(65, 80, default=70, space="sell")
    
    regime_lookback = IntParameter(50, 200, default=100, space="buy")
    
    cooldown_lookback = IntParameter(2, 48, default=5, space="protection")
    stop_duration = IntParameter(12, 200, default=5, space="protection")
    use_stop_protection = BooleanParameter(default=True, space="protection")

    _indicator_cache = {}
    _last_candle_cache = {}

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Enhanced dynamic stoploss based on volatility and market conditions
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
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
        
        return max(dynamic_stoploss, -0.15)  # Never worse than -15%

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Enhanced indicator calculation with performance optimization
        """
        pair = metadata['pair']
        
        cache_key = f"{pair}_{len(dataframe)}"
        if cache_key in self._indicator_cache:
            cached_df = self._indicator_cache[cache_key]
            if len(cached_df) == len(dataframe):
                return cached_df
        
        dataframe['RSI_14'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['RSI_4'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['RSI_20'] = ta.RSI(dataframe, timeperiod=20)
        
        dataframe['EMA_8'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['EMA_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['EMA_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['EMA_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['EMA_200'] = ta.EMA(dataframe, timeperiod=200)
        
        dataframe['SMA_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['SMA_50'] = ta.SMA(dataframe, timeperiod=50)
        
        dataframe['ATR_14'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['NATR_14'] = ta.NATR(dataframe, timeperiod=14)
        
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['BB_lower'] = bollinger['lower']
        dataframe['BB_middle'] = bollinger['mid']
        dataframe['BB_upper'] = bollinger['upper']
        dataframe['BB_width'] = (dataframe['BB_upper'] - dataframe['BB_lower']) / dataframe['BB_middle']
        dataframe['BB_squeeze'] = dataframe['BB_width'] < dataframe['BB_width'].rolling(20).quantile(0.2)
        
        dataframe['VWAP'] = qtpylib.vwap(dataframe)
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        dataframe['MACD'], dataframe['MACD_signal'], dataframe['MACD_hist'] = ta.MACD(dataframe)
        dataframe['MACD_cross_above'] = qtpylib.crossed_above(dataframe['MACD'], dataframe['MACD_signal'])
        dataframe['MACD_cross_below'] = qtpylib.crossed_below(dataframe['MACD'], dataframe['MACD_signal'])
        
        stoch = ta.STOCH(dataframe)
        dataframe['STOCH_k'] = stoch['slowk']
        dataframe['STOCH_d'] = stoch['slowd']
        
        dataframe['WILLR_14'] = ta.WILLR(dataframe, timeperiod=14)
        
        dataframe['trend_strength'] = abs(dataframe['EMA_20'] - dataframe['EMA_50']) / dataframe['close']
        dataframe['is_trending'] = dataframe['trend_strength'] > self.trend_strength_threshold.value
        dataframe['trend_direction'] = np.where(dataframe['EMA_20'] > dataframe['EMA_50'], 1, -1)
        
        dataframe['volume_trend'] = dataframe['volume'].rolling(window=10).mean() / dataframe['volume'].rolling(window=30).mean()
        dataframe['price_volume_trend'] = ta.AD(dataframe)
        
        dataframe['pivot_high'] = dataframe['high'].rolling(window=5, center=True).max() == dataframe['high']
        dataframe['pivot_low'] = dataframe['low'].rolling(window=5, center=True).min() == dataframe['low']
        
        dataframe = self._calculate_enhanced_protections(dataframe)
        
        dataframe = self._populate_informative_indicators(dataframe, metadata)
        
        self._indicator_cache[cache_key] = dataframe.copy()
        
        return dataframe

    def _calculate_enhanced_protections(self, dataframe: DataFrame) -> DataFrame:
        """
        Enhanced protection calculations
        """
        dataframe['volatility_protection'] = dataframe['NATR_14'] > dataframe['NATR_14'].rolling(50).quantile(0.8)
        
        dataframe['volume_protection'] = dataframe['volume_ratio'] < 0.5
        
        dataframe['momentum_protection'] = (
            (dataframe['RSI_14'] > 80) | 
            (dataframe['RSI_14'] < 20) |
            (dataframe['WILLR_14'] > -10) |
            (dataframe['WILLR_14'] < -90)
        )
        
        dataframe['enhanced_protection'] = (
            dataframe['volatility_protection'] |
            dataframe['volume_protection'] |
            dataframe['momentum_protection']
        )
        
        return dataframe

    def _populate_informative_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add informative timeframe indicators
        """
        for timeframe in self.informative_timeframes:
            informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=timeframe)
            
            informative[f'RSI_14_{timeframe}'] = ta.RSI(informative, timeperiod=14)
            informative[f'EMA_20_{timeframe}'] = ta.EMA(informative, timeperiod=20)
            informative[f'EMA_50_{timeframe}'] = ta.EMA(informative, timeperiod=50)
            
            dataframe = merge_informative_pair(dataframe, informative, self.timeframe, timeframe, ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Enhanced entry conditions with confluence scoring
        """
        conditions = []
        
        long_conditions = [
            (dataframe['EMA_8'] > dataframe['EMA_20']),
            (dataframe['EMA_20'] > dataframe['EMA_50']),
            (dataframe['close'] > dataframe['VWAP']),
            
            (dataframe['RSI_14'] > self.rsi_oversold.value) & (dataframe['RSI_14'] < 60),
            (dataframe['MACD'] > dataframe['MACD_signal']),
            (dataframe['STOCH_k'] > dataframe['STOCH_d']),
            
            (dataframe['volume_ratio'] > self.volume_threshold.value),
            (dataframe['volume_trend'] > 1.0),
            
            (~dataframe['BB_squeeze']),  # Not in squeeze
            (dataframe['ATR_14'] > dataframe['ATR_14'].shift(1)),  # Increasing volatility
            
            (~dataframe['enhanced_protection']),
            (dataframe['is_trending']),
            (dataframe['trend_direction'] > 0),
        ]
        
        confluence_score = sum(long_conditions)
        min_confluence = 8  # Require at least 8 out of 13 conditions
        
        dataframe.loc[
            (confluence_score >= min_confluence) &
            (dataframe['volume'] > 0),
            'enter_long'
        ] = 1
        
        short_conditions = [
            (dataframe['EMA_8'] < dataframe['EMA_20']),
            (dataframe['EMA_20'] < dataframe['EMA_50']),
            (dataframe['close'] < dataframe['VWAP']),
            
            (dataframe['RSI_14'] < self.rsi_overbought.value) & (dataframe['RSI_14'] > 40),
            (dataframe['MACD'] < dataframe['MACD_signal']),
            (dataframe['STOCH_k'] < dataframe['STOCH_d']),
            
            (dataframe['volume_ratio'] > self.volume_threshold.value),
            
            (~dataframe['enhanced_protection']),
            (dataframe['is_trending']),
            (dataframe['trend_direction'] < 0),
        ]
        
        short_confluence_score = sum(short_conditions)
        min_short_confluence = 7
        
        dataframe.loc[
            (short_confluence_score >= min_short_confluence) &
            (dataframe['volume'] > 0),
            'enter_short'
        ] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Enhanced exit conditions with dynamic take-profit levels
        """
        long_exit_conditions = [
            (dataframe['RSI_14'] > self.rsi_overbought.value),
            (dataframe['MACD_cross_below']),
            (dataframe['STOCH_k'] < dataframe['STOCH_d']) & (dataframe['STOCH_k'] > 80),
            
            (dataframe['EMA_8'] < dataframe['EMA_20']),
            (dataframe['close'] < dataframe['VWAP']),
            
            (dataframe['volume_ratio'] < 0.5) & (dataframe['close'] > dataframe['close'].shift(1)),
            
            (dataframe['enhanced_protection']),
        ]
        
        long_exit_score = sum(long_exit_conditions)
        
        dataframe.loc[
            (long_exit_score >= 3),  # Require at least 3 exit signals
            'exit_long'
        ] = 1
        
        short_exit_conditions = [
            (dataframe['RSI_14'] < self.rsi_oversold.value),
            (dataframe['MACD_cross_above']),
            (dataframe['STOCH_k'] > dataframe['STOCH_d']) & (dataframe['STOCH_k'] < 20),
            
            (dataframe['EMA_8'] > dataframe['EMA_20']),
            (dataframe['close'] > dataframe['VWAP']),
            
            (dataframe['enhanced_protection']),
        ]
        
        short_exit_score = sum(short_exit_conditions)
        
        dataframe.loc[
            (short_exit_score >= 3),
            'exit_short'
        ] = 1
        
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                           side: str, **kwargs) -> bool:
        """
        Enhanced trade entry confirmation with additional safety checks
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if len(dataframe) < 1:
            return False
            
        last_candle = dataframe.iloc[-1].squeeze()
        
        if last_candle['enhanced_protection']:
            return False
            
        if last_candle['NATR_14'] > 0.05:  # 5% normalized ATR threshold
            return False
            
        if last_candle['volume_ratio'] < 0.8:
            return False
            
        return True

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                            current_rate: float, current_profit: float,
                            min_stake: Optional[float], max_stake: float,
                            current_entry_rate: float, current_exit_rate: float,
                            current_entry_profit: float, current_exit_profit: float,
                            **kwargs) -> Optional[float]:
        """
        Enhanced position adjustment logic
        """
        if current_profit > -0.05 and current_profit < -0.02:
            dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            
            if (last_candle['RSI_14'] < 40 and 
                last_candle['EMA_8'] > last_candle['EMA_20'] and
                not last_candle['enhanced_protection']):
                return trade.stake_amount * 0.5  # Add 50% of original position
                
        return None

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                side: str, **kwargs) -> float:
        """
        Dynamic leverage based on market conditions
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if len(dataframe) < 1:
            return 1.0
            
        last_candle = dataframe.iloc[-1].squeeze()
        
        if last_candle['NATR_14'] > 0.03:
            return min(proposed_leverage * 0.5, max_leverage)
        elif last_candle['NATR_14'] > 0.02:
            return min(proposed_leverage * 0.75, max_leverage)
        else:
            return min(proposed_leverage, max_leverage)
