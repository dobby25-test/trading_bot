"""
Trade Tracker — Tracks all trades, win rate, and statistics
Saves everything to trades.json for persistence
"""

import json
import os
import logging
from datetime import datetime

log = logging.getLogger(__name__)
TRADES_FILE = "logs/trades.json"

class TradeTracker:
    def __init__(self):
        os.makedirs("logs", exist_ok=True)
        self.trades = self._load()

    def _load(self) -> dict:
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {"open": {}, "closed": []}

    def _save(self):
        with open(TRADES_FILE, "w") as f:
            json.dump(self.trades, f, indent=2)

    def add_trade(self, trade: dict):
        self.trades["open"][trade["pair"]] = trade
        self._save()
        log.info(f"📝 Trade logged: {trade['pair']} {trade['direction']} @ {trade['entry']}")

    def close_trade(self, pair: str, exit_price: float, reason: str):
        trade = self.trades["open"].pop(pair, None)
        if not trade:
            return
        trade["exit"]       = exit_price
        trade["exit_time"]  = datetime.now().isoformat()
        trade["reason"]     = reason
        trade["result"]     = "WIN" if reason == "TP" else "LOSS"
        if trade["direction"] == "BUY":
            trade["pnl"] = round((exit_price - trade["entry"]) * trade["qty"], 4)
        else:
            trade["pnl"] = round((trade["entry"] - exit_price) * trade["qty"], 4)
        self.trades["closed"].append(trade)
        self._save()
        log.info(f"🏁 Closed: {pair} | {trade['result']} | PnL: {trade['pnl']:+.4f}")

    def has_open_trade(self, pair: str) -> bool:
        return pair in self.trades["open"]

    def get_open_trade(self, pair: str) -> dict:
        return self.trades["open"].get(pair)

    def get_stats(self) -> dict:
        closed = self.trades["closed"]
        total  = len(closed)
        wins   = sum(1 for t in closed if t["result"] == "WIN")
        losses = total - wins
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        win_rate  = (wins / total * 100) if total > 0 else 0.0

        return {
            "total":     total,
            "wins":      wins,
            "losses":    losses,
            "win_rate":  round(win_rate, 1),
            "total_pnl": round(total_pnl, 4),
            "open":      len(self.trades["open"]),
        }

    def print_report(self):
        s = self.get_stats()
        print("\n" + "="*45)
        print("       📊 TRADING BOT PERFORMANCE")
        print("="*45)
        print(f"  Total Trades : {s['total']}")
        print(f"  Wins         : {s['wins']} ✅")
        print(f"  Losses       : {s['losses']} ❌")
        print(f"  Win Rate     : {s['win_rate']}%")
        print(f"  Total PnL    : {s['total_pnl']:+.4f} USDT")
        print(f"  Open Trades  : {s['open']}")
        print("="*45 + "\n")