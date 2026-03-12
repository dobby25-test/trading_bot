"""
Strategy Engine — Professional Multi-Indicator System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Indicators used:
  1. RSI (14)                — Oversold / Overbought momentum
  2. EMA 9/21 Crossover      — Short-term trend & entries
  3. EMA 200                  — Big-picture trend filter
  4. MACD (12, 26, 9)         — Momentum confirmation
  5. Bollinger Bands (20, 2)  — Volatility squeeze & breakout
  6. ATR (14)                 — Volatility for dynamic SL/TP
  7. Volume Filter            — Confirms genuine moves

Signal Logic:
  BUY  = RSI < 35 + EMA bullish + MACD bullish + price near lower band + volume OK + EMA200 uptrend
  SELL = RSI > 65 + EMA bearish + MACD bearish + price near upper band + volume OK + EMA200 downtrend
  
  Scoring system: each indicator adds points. Trade only when score >= threshold.
"""

import pandas as pd
import numpy as np
import logging
from config import CONFIG

log = logging.getLogger(__name__)

class Strategy:
    def __init__(self):
        # RSI
        self.rsi_period     = CONFIG["RSI_PERIOD"]
        self.rsi_oversold   = CONFIG["RSI_OVERSOLD"]
        self.rsi_overbought = CONFIG["RSI_OVERBOUGHT"]
        # EMA short-term
        self.ema_fast = CONFIG["EMA_FAST"]
        self.ema_slow = CONFIG["EMA_SLOW"]
        # EMA long-term trend filter
        self.ema_trend_period = 200
        # MACD
        self.macd_fast   = 12
        self.macd_slow   = 26
        self.macd_signal = 9
        # Bollinger Bands
        self.bb_period = 20
        self.bb_std    = 2.0
        # ATR
        self.atr_period = 14
        # Score threshold: need at least this many confirmations to trade
        self.buy_threshold  = 3
        self.sell_threshold = 3

    def get_signal(self, df: pd.DataFrame) -> dict:
        """Multi-indicator scoring engine. Returns direction + all indicator data."""
        df = df.copy()
        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        # ── 1. RSI ────────────────────────────────────────────────
        rsi = self._calculate_rsi(close)
        current_rsi = rsi.iloc[-1]

        # ── 2. EMA 9/21 ──────────────────────────────────────────
        ema_fast = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow, adjust=False).mean()
        fast_now, fast_prev = ema_fast.iloc[-1], ema_fast.iloc[-2]
        slow_now, slow_prev = ema_slow.iloc[-1], ema_slow.iloc[-2]

        ema_trend = "BULLISH" if fast_now > slow_now else "BEARISH"
        ema_crossover_up   = fast_prev < slow_prev and fast_now > slow_now
        ema_crossover_down = fast_prev > slow_prev and fast_now < slow_now

        # ── 3. EMA 200 (big-picture trend) ────────────────────────
        ema_200 = close.ewm(span=self.ema_trend_period, adjust=False).mean()
        price_above_200 = close.iloc[-1] > ema_200.iloc[-1]
        big_trend = "UPTREND" if price_above_200 else "DOWNTREND"

        # ── 4. MACD ───────────────────────────────────────────────
        macd_line, signal_line, macd_hist = self._calculate_macd(close)
        macd_bullish = macd_hist.iloc[-1] > 0 and macd_hist.iloc[-1] > macd_hist.iloc[-2]
        macd_bearish = macd_hist.iloc[-1] < 0 and macd_hist.iloc[-1] < macd_hist.iloc[-2]
        macd_cross_up   = macd_hist.iloc[-2] <= 0 < macd_hist.iloc[-1]
        macd_cross_down = macd_hist.iloc[-2] >= 0 > macd_hist.iloc[-1]

        # ── 5. Bollinger Bands ────────────────────────────────────
        bb_mid, bb_upper, bb_lower = self._calculate_bollinger(close)
        current_price = close.iloc[-1]
        bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1]
        # Price position within bands (0 = lower band, 1 = upper band)
        bb_position = (current_price - bb_lower.iloc[-1]) / max(bb_upper.iloc[-1] - bb_lower.iloc[-1], 0.001)
        near_lower = bb_position < 0.2   # near lower band
        near_upper = bb_position > 0.8   # near upper band
        # Squeeze: bands very tight → breakout likely
        bb_squeeze = bb_width < 0.03

        # ── 6. ATR ────────────────────────────────────────────────
        atr = self._calculate_atr(high, low, close)
        current_atr = atr.iloc[-1]

        # ── 7. Volume ─────────────────────────────────────────────
        avg_volume     = df["volume"].iloc[-20:].mean()
        current_volume = df["volume"].iloc[-1]
        volume_ok      = current_volume > avg_volume * 0.8  # Slightly relaxed (was 1.2x)
        volume_surge   = current_volume > avg_volume * 1.5  # Strong volume

        # ══════════════════════════════════════════════════════════
        # SCORING SYSTEM — each True condition adds +1
        # ══════════════════════════════════════════════════════════
        buy_score = 0
        sell_score = 0

        # RSI
        if current_rsi < self.rsi_oversold:
            buy_score += 1
        if current_rsi > self.rsi_overbought:
            sell_score += 1

        # EMA trend
        if ema_trend == "BULLISH":
            buy_score += 1
        if ema_trend == "BEARISH":
            sell_score += 1

        # EMA crossover (bonus)
        if ema_crossover_up:
            buy_score += 1
        if ema_crossover_down:
            sell_score += 1

        # EMA 200 trend filter
        if big_trend == "UPTREND":
            buy_score += 1
        if big_trend == "DOWNTREND":
            sell_score += 1

        # MACD
        if macd_bullish or macd_cross_up:
            buy_score += 1
        if macd_bearish or macd_cross_down:
            sell_score += 1

        # Bollinger Bands
        if near_lower:
            buy_score += 1
        if near_upper:
            sell_score += 1

        # Volume
        if volume_surge:
            buy_score += 1
            sell_score += 1

        # ── Final Direction ────────────────────────────────────────
        direction = "HOLD"
        if buy_score >= self.buy_threshold and volume_ok:
            direction = "BUY"
        elif sell_score >= self.sell_threshold and volume_ok:
            direction = "SELL"

        # Log the score breakdown
        if direction != "HOLD":
            log.info(
                f"🎯 {direction} score: BUY={buy_score} SELL={sell_score} | "
                f"RSI={current_rsi:.1f} MACD={'↑' if macd_bullish else '↓'} "
                f"BB={bb_position:.2f} Trend={big_trend} Vol={'✓' if volume_ok else '✗'}"
            )
        elif buy_score >= 2 or sell_score >= 2:
            log.info(
                f"📊 Near signal: BUY={buy_score}/{self.buy_threshold} "
                f"SELL={sell_score}/{self.sell_threshold}"
            )

        return {
            "direction":     direction,
            "rsi":           current_rsi,
            "ema_trend":     ema_trend,
            "ema_fast":      fast_now,
            "ema_slow":      slow_now,
            "big_trend":     big_trend,
            "macd_hist":     macd_hist.iloc[-1],
            "macd_bullish":  macd_bullish,
            "bb_position":   bb_position,
            "bb_squeeze":    bb_squeeze,
            "atr":           current_atr,
            "volume_ok":     volume_ok,
            "buy_score":     buy_score,
            "sell_score":    sell_score,
            "crossover_up":  ema_crossover_up,
            "crossover_dn":  ema_crossover_down,
        }

    # ── Indicator Calculations ────────────────────────────────────

    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        delta    = prices.diff()
        gain     = delta.clip(lower=0)
        loss     = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=self.rsi_period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=self.rsi_period - 1, adjust=False).mean()
        rs  = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _calculate_macd(self, prices: pd.Series):
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line   = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram   = macd_line - signal_line
        return macd_line, signal_line, histogram

    def _calculate_bollinger(self, prices: pd.Series):
        mid   = prices.rolling(window=self.bb_period).mean()
        std   = prices.rolling(window=self.bb_period).std()
        upper = mid + (self.bb_std * std)
        lower = mid - (self.bb_std * std)
        return mid, upper, lower

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low  - close.shift(1)).abs()
        tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(span=self.atr_period, adjust=False).mean()
        return atr