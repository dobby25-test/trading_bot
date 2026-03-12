"""
╔══════════════════════════════════════════════════════════════╗
║          SMART BINANCE TRADING BOT - by Palak               ║
║   Strategy: RSI + EMA + News Sentiment + Risk Management    ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import time
import logging
import json
import os
from datetime import datetime
from config import CONFIG
from data_fetcher import DataFetcher
from strategy import Strategy
from news_analyzer import NewsAnalyzer
from risk_manager import RiskManager
from trade_executor import TradeExecutor
from tracker import TradeTracker
from notifier import Notifier

# ─── Create logs folder if it doesn't exist ──────────────────
os.makedirs("logs", exist_ok=True)

# ─── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1))
    ]
)
log = logging.getLogger(__name__)

# ─── Main Bot Class ────────────────────────────────────────────
class TradingBot:
    def __init__(self):
        log.info("🚀 Initializing Smart Trading Bot...")
        self.config       = CONFIG
        self.fetcher      = DataFetcher()
        self.strategy     = Strategy()
        self.news         = NewsAnalyzer()
        self.risk         = RiskManager()
        self.executor     = TradeExecutor()
        self.tracker      = TradeTracker()
        self.notifier     = Notifier()
        self.running      = True
        log.info(f"✅ Bot ready | Mode: {'PAPER' if CONFIG['PAPER_TRADING'] else '🔴 LIVE'} | Pairs: {CONFIG['TRADING_PAIRS']}")

    def run(self):
        log.info("▶️  Bot started. Press Ctrl+C to stop.")
        pairs_str = ', '.join(CONFIG['TRADING_PAIRS'])
        mode_str  = '📄 PAPER' if CONFIG['PAPER_TRADING'] else '🔴 LIVE'
        self.notifier.send(
            f"🚀 *Bot Started!*\n"
            f"Mode: {mode_str}\n"
            f"Pairs: `{pairs_str}`\n"
            f"Timeframe: `{CONFIG['TIMEFRAME']}` | Interval: `{CONFIG['CHECK_INTERVAL']}s`"
        )

        while self.running:
            try:
                scan_results = []
                for pair in CONFIG["TRADING_PAIRS"]:
                    result = self._process_pair(pair)
                    if result:
                        scan_results.append(result)

                # Send per-cycle scan summary to Telegram
                if scan_results:
                    self.notifier.send_scan_summary(scan_results)

                # Send daily report at midnight
                now = datetime.now()
                if now.hour == 0 and now.minute < 5:
                    self._send_daily_report()

                log.info(f"⏳ Sleeping {CONFIG['CHECK_INTERVAL']}s...\n{'─'*50}")
                time.sleep(CONFIG["CHECK_INTERVAL"])

            except KeyboardInterrupt:
                log.info("🛑 Bot stopped by user.")
                self.notifier.send("🛑 *Bot stopped.*")
                self.running = False
            except Exception as e:
                log.error(f"❌ Main loop error: {e}")
                time.sleep(30)

    def _process_pair(self, pair: str) -> dict:
        log.info(f"\n📊 Analyzing {pair}...")

        # 1. Fetch price data
        df = self.fetcher.get_klines(pair, CONFIG["TIMEFRAME"], limit=100)
        if df is None or df.empty:
            log.warning(f"⚠️  No data for {pair}")
            return None

        current_price = float(df["close"].iloc[-1])
        log.info(f"💰 {pair} price: {current_price:.4f}")

        # 2. Calculate technical signals
        signal = self.strategy.get_signal(df)
        log.info(f"📈 Technical Signal: {signal['direction']} | RSI: {signal['rsi']:.1f} | EMA: {signal['ema_trend']}")

        # 3. News sentiment
        sentiment = self.news.get_sentiment(pair.replace("USDT", ""))
        log.info(f"📰 News Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")

        # 4. Combined decision
        decision = self._make_decision(signal, sentiment, pair)
        log.info(f"🧠 Decision: {decision}")

        # 5. Execute if signal is strong
        if decision in ["BUY", "SELL"]:
            self._execute_trade(pair, decision, current_price, signal)

        # 6. Check open trades for exit
        self._check_exits(pair, current_price)

        # Return scan result for summary
        return {
            "pair":      pair,
            "price":     current_price,
            "signal":    signal["direction"],
            "rsi":       signal["rsi"],
            "ema":       signal["ema_trend"],
            "sentiment": sentiment["label"],
            "decision":  decision,
        }

    def _make_decision(self, signal: dict, sentiment: dict, pair: str) -> str:
        """
        Multi-layer decision engine:
        - Technical signal must be BUY or SELL
        - News sentiment must not be strongly against the trade
        - No existing open trade for this pair
        """
        direction = signal["direction"]

        # Skip if already in a trade for this pair
        if self.tracker.has_open_trade(pair):
            log.info(f"⏸️  Already in trade for {pair}, skipping.")
            return "HOLD"

        # Skip if RSI is in neutral zone
        if direction == "HOLD":
            return "HOLD"

        # News filter: block BUY on very negative news, block SELL on very positive news
        if direction == "BUY" and sentiment["score"] < -0.3:
            log.info("📰 Blocking BUY — negative news sentiment")
            return "HOLD"
        if direction == "SELL" and sentiment["score"] > 0.3:
            log.info("📰 Blocking SELL — positive news sentiment")
            return "HOLD"

        # Require EMA trend to agree
        if direction == "BUY" and signal["ema_trend"] != "BULLISH":
            log.info("📉 Blocking BUY — EMA not bullish")
            return "HOLD"
        if direction == "SELL" and signal["ema_trend"] != "BEARISH":
            log.info("📈 Blocking SELL — EMA not bearish")
            return "HOLD"

        return direction

    def _execute_trade(self, pair: str, direction: str, price: float, signal: dict):
        balance = self.executor.get_balance()
        # Pass ATR and signal score for dynamic SL/TP
        atr = signal.get("atr", None)
        strength = signal.get("buy_score", 0) if direction == "BUY" else signal.get("sell_score", 0)
        qty, sl, tp = self.risk.calculate_position(price, direction, balance, atr=atr, signal_strength=strength)

        if qty <= 0:
            log.warning("⚠️  Position size too small, skipping trade.")
            return

        log.info(f"{'🟢 BUY' if direction == 'BUY' else '🔴 SELL'} {pair} | Qty: {qty} | SL: {sl:.4f} | TP: {tp:.4f}")

        result = self.executor.place_order(pair, direction, qty, price)
        if result:
            trade = {
                "pair":      pair,
                "direction": direction,
                "entry":     price,
                "qty":       qty,
                "sl":        sl,
                "tp":        tp,
                "time":      datetime.now().isoformat(),
                "rsi":       signal["rsi"],
                "order_id":  result.get("orderId", "PAPER")
            }
            self.tracker.add_trade(trade)
            # Send rich Telegram alert
            if direction == "BUY":
                self.notifier.send_buy(pair, price, qty, sl, tp, signal["rsi"], balance)
            else:
                self.notifier.send_sell(pair, price, qty, sl, tp, signal["rsi"], balance)

    def _check_exits(self, pair: str, current_price: float):
        trade = self.tracker.get_open_trade(pair)
        if not trade:
            return

        hit_tp = hit_sl = False
        if trade["direction"] == "BUY":
            hit_tp = current_price >= trade["tp"]
            hit_sl = current_price <= trade["sl"]
        else:
            hit_tp = current_price <= trade["tp"]
            hit_sl = current_price >= trade["sl"]

        if hit_tp or hit_sl:
            pnl    = self.risk.calculate_pnl(trade, current_price)
            self.tracker.close_trade(pair, current_price, "TP" if hit_tp else "SL")
            stats   = self.tracker.get_stats()
            balance = self.executor.get_balance()
            outcome = "WIN ✅" if hit_tp else "LOSS ❌"
            log.info(f"🏁 Trade closed: {outcome} | PnL: {pnl:+.2f} USDT")
            if hit_tp:
                self.notifier.send_tp_hit(
                    pair, trade["entry"], current_price,
                    pnl, stats["wins"], stats["losses"], stats["win_rate"], balance
                )
            else:
                self.notifier.send_sl_hit(
                    pair, trade["entry"], current_price,
                    pnl, stats["wins"], stats["losses"], stats["win_rate"], balance
                )

    def _send_daily_report(self):
        stats   = self.tracker.get_stats()
        balance = self.executor.get_balance()
        log.info(
            f"📊 Daily Report | Trades: {stats['total']} | "
            f"W/L: {stats['wins']}/{stats['losses']} | "
            f"PnL: {stats['total_pnl']:+.2f} | Balance: ${balance:.2f}"
        )
        self.notifier.send_daily_report(
            stats["total"], stats["wins"], stats["losses"],
            stats["win_rate"], stats["total_pnl"], balance
        )


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    bot = TradingBot()
    bot.run()