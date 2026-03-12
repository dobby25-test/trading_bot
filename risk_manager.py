"""
Risk Manager — Smart Position Sizing + ATR-Based Dynamic SL/TP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Key features:
  - ATR-based SL: adapts to each coin's current volatility
  - Risk-reward ratio: TP = 2× the SL distance (or 3× on strong signals)
  - Position sizing: risks exactly X% of balance per trade
  - Daily loss limit: stops trading if losses hit 5% of balance
  - Falls back to config % if ATR not available
"""

import logging
from config import CONFIG

log = logging.getLogger(__name__)

class RiskManager:
    def __init__(self):
        self.risk_pct         = CONFIG["RISK_PER_TRADE_PCT"] / 100
        self.sl_pct           = CONFIG["STOP_LOSS_PCT"] / 100       # fallback
        self.tp_pct           = CONFIG["TAKE_PROFIT_PCT"] / 100     # fallback
        self.daily_loss_limit = CONFIG["MAX_DAILY_LOSS_PCT"] / 100
        self.daily_loss       = 0.0
        # ATR multiplier: SL = price ± (ATR × multiplier)
        self.atr_sl_multiplier = 1.5
        self.risk_reward_ratio = 2.0   # TP = 2× SL distance

    def calculate_position(self, price: float, direction: str, balance: float,
                           atr: float = None, signal_strength: int = 0):
        """
        Calculate position size, SL, and TP.
        If ATR is provided → uses dynamic volatility-based levels.
        If not → falls back to fixed config percentages.
        signal_strength: the score from strategy — higher = better risk/reward.
        """
        if balance <= 0:
            return 0, 0, 0

        # Check daily loss limit
        if self.daily_loss >= balance * self.daily_loss_limit:
            log.warning("🛑 Daily loss limit reached! Blocking new trades.")
            return 0, 0, 0

        # Risk amount in USDT
        risk_amount = balance * self.risk_pct

        # ── Dynamic SL/TP using ATR ──────────────────────────────
        if atr and atr > 0:
            sl_distance = atr * self.atr_sl_multiplier
            # Better signals → wider TP for more profit capture
            rr_ratio = self.risk_reward_ratio
            if signal_strength >= 5:
                rr_ratio = 3.0   # Strong signal → ride the trend
            elif signal_strength >= 4:
                rr_ratio = 2.5
            tp_distance = sl_distance * rr_ratio

            if direction == "BUY":
                sl = round(price - sl_distance, 4)
                tp = round(price + tp_distance, 4)
            else:
                sl = round(price + sl_distance, 4)
                tp = round(price - tp_distance, 4)

            log.info(
                f"📐 ATR-based stops | ATR={atr:.4f} | "
                f"SL dist={sl_distance:.4f} | TP dist={tp_distance:.4f} | RR=1:{rr_ratio}"
            )
        else:
            # Fallback: fixed % from config
            sl_distance = price * self.sl_pct
            if direction == "BUY":
                sl = round(price * (1 - self.sl_pct), 4)
                tp = round(price * (1 + self.tp_pct), 4)
            else:
                sl = round(price * (1 + self.sl_pct), 4)
                tp = round(price * (1 - self.tp_pct), 4)

        # Position sizing: risk_amount / SL_distance = qty
        qty = round(risk_amount / max(sl_distance, 0.0001), 6)

        log.info(f"💼 Position: {qty} | Risk: ${risk_amount:.2f} | SL: {sl} | TP: {tp}")
        return qty, sl, tp

    def calculate_pnl(self, trade: dict, exit_price: float) -> float:
        """Calculate profit/loss for a closed trade"""
        entry = trade["entry"]
        qty   = trade["qty"]

        if trade["direction"] == "BUY":
            pnl = (exit_price - entry) * qty
        else:
            pnl = (entry - exit_price) * qty

        # Update daily loss tracker
        if pnl < 0:
            self.daily_loss += abs(pnl)

        return round(pnl, 4)

    def reset_daily_loss(self):
        self.daily_loss = 0.0