"""
Notifier — Sends detailed trade alerts to Telegram
Covers: BUY, SELL, TP hit, SL hit, HOLD scans, daily report
"""

import requests
import logging
from datetime import datetime
from config import CONFIG

log = logging.getLogger(__name__)

def _esc(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text

class Notifier:
    def __init__(self):
        self.token   = CONFIG.get("TELEGRAM_TOKEN", "")
        self.chat_id = CONFIG.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        if self.enabled:
            log.info("[OK] Telegram alerts enabled")
        else:
            log.info("[--] Telegram alerts disabled (set TELEGRAM_TOKEN + TELEGRAM_CHAT_ID)")

    # ── Generic send ──────────────────────────────────────────────────────────
    def send(self, message: str):
        """Send a plain-text message to Telegram."""
        self._post(f"🤖 *TradingBot*\n\n{message}", parse_mode="Markdown")

    # ── Specialised alert helpers ─────────────────────────────────────────────
    def send_buy(self, pair: str, price: float, qty: float,
                 sl: float, tp: float, rsi: float, balance: float):
        msg = (
            f"🟢 *BUY SIGNAL EXECUTED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair:       `{pair}`\n"
            f"💰 Entry:      `{price:.4f}`\n"
            f"📦 Quantity:   `{qty}`\n"
            f"🛑 Stop Loss:  `{sl:.4f}`\n"
            f"🎯 Take Profit:`{tp:.4f}`\n"
            f"📊 RSI:        `{rsi:.1f}`\n"
            f"💼 Balance:    `${balance:.2f}`\n"
            f"🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`"
        )
        self._post(msg, parse_mode="Markdown")

    def send_sell(self, pair: str, price: float, qty: float,
                  sl: float, tp: float, rsi: float, balance: float):
        msg = (
            f"🔴 *SELL SIGNAL EXECUTED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair:       `{pair}`\n"
            f"💰 Entry:      `{price:.4f}`\n"
            f"📦 Quantity:   `{qty}`\n"
            f"🛑 Stop Loss:  `{sl:.4f}`\n"
            f"🎯 Take Profit:`{tp:.4f}`\n"
            f"📊 RSI:        `{rsi:.1f}`\n"
            f"💼 Balance:    `${balance:.2f}`\n"
            f"🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`"
        )
        self._post(msg, parse_mode="Markdown")

    def send_tp_hit(self, pair: str, entry: float, exit_price: float,
                    pnl: float, wins: int, losses: int, win_rate: float, balance: float):
        msg = (
            f"✅ *TAKE PROFIT HIT — WIN!*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair:       `{pair}`\n"
            f"📈 Entry:      `{entry:.4f}`\n"
            f"📤 Exit:       `{exit_price:.4f}`\n"
            f"💵 PnL:        `{pnl:+.2f} USDT`\n"
            f"📊 Win Rate:   `{win_rate:.1f}%` ({wins}W / {losses}L)\n"
            f"💼 Balance:    `${balance:.2f}`\n"
            f"🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`"
        )
        self._post(msg, parse_mode="Markdown")

    def send_sl_hit(self, pair: str, entry: float, exit_price: float,
                    pnl: float, wins: int, losses: int, win_rate: float, balance: float):
        msg = (
            f"❌ *STOP LOSS HIT — LOSS*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair:       `{pair}`\n"
            f"📈 Entry:      `{entry:.4f}`\n"
            f"📤 Exit:       `{exit_price:.4f}`\n"
            f"💵 PnL:        `{pnl:+.2f} USDT`\n"
            f"📊 Win Rate:   `{win_rate:.1f}%` ({wins}W / {losses}L)\n"
            f"💼 Balance:    `${balance:.2f}`\n"
            f"🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`"
        )
        self._post(msg, parse_mode="Markdown")

    def send_scan_summary(self, results: list):
        """
        Send a compact per-scan summary of all pairs.
        results = [{"pair": str, "price": float, "signal": str, "rsi": float,
                    "ema": str, "sentiment": str, "decision": str}, ...]
        """
        lines = ["📡 *Scan Summary*", f"🕐 `{datetime.now().strftime('%H:%M:%S')}`", ""]
        for r in results:
            decision_icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⏸"}.get(r["decision"], "❓")
            lines.append(
                f"{decision_icon} `{r['pair']}` — ${r['price']:.4f}\n"
                f"   RSI: `{r['rsi']:.1f}` | EMA: `{r['ema']}` | "
                f"News: `{r['sentiment']}` | → *{r['decision']}*"
            )
        self._post("\n".join(lines), parse_mode="Markdown")

    def send_daily_report(self, total: int, wins: int, losses: int,
                          win_rate: float, total_pnl: float, balance: float):
        msg = (
            f"📊 *Daily Report — {datetime.now().strftime('%Y-%m-%d')}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 Total Trades: `{total}`\n"
            f"✅ Wins:         `{wins}`\n"
            f"❌ Losses:       `{losses}`\n"
            f"🎯 Win Rate:     `{win_rate:.1f}%`\n"
            f"💵 Total PnL:    `{total_pnl:+.2f} USDT`\n"
            f"💼 Balance:      `${balance:.2f}`"
        )
        self._post(msg, parse_mode="Markdown")

    # ── Internal post ─────────────────────────────────────────────────────────
    def _post(self, text: str, parse_mode: str = ""):
        if not self.enabled:
            log.info(f"[ALERT] {text}")
            return
        try:
            payload = {"chat_id": self.chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data=payload,
                timeout=10
            )
            if r.status_code == 200:
                return
            # Auto-discover chat_id if the configured one is wrong
            if self._should_retry_with_discovered_chat(r.text):
                discovered = self._discover_user_chat_id()
                if discovered:
                    self.chat_id = str(discovered)
                    payload["chat_id"] = self.chat_id
                    retry = requests.post(
                        f"https://api.telegram.org/bot{self.token}/sendMessage",
                        data=payload,
                        timeout=10
                    )
                    if retry.status_code == 200:
                        log.info(f"[OK] Telegram chat_id auto-updated to {self.chat_id}")
                        return
                    log.warning(f"⚠️  Telegram retry failed: {retry.text}")
                    return
            log.warning(f"⚠️  Telegram send failed: {r.text}")
        except Exception as e:
            log.warning(f"⚠️  Telegram error: {e}")

    def _should_retry_with_discovered_chat(self, response_text: str) -> bool:
        text = (response_text or "").lower()
        return "bots can't send messages to bots" in text or "chat not found" in text

    def _discover_user_chat_id(self):
        """Try to find a recent private user chat id from Telegram updates."""
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                timeout=10
            )
            if r.status_code != 200:
                return None
            updates = r.json().get("result", [])
            for item in reversed(updates):
                msg = item.get("message") or item.get("edited_message") or {}
                chat  = msg.get("chat", {})
                sender = msg.get("from", {})
                if chat.get("type") == "private" and not sender.get("is_bot", False):
                    return chat.get("id")
        except Exception as e:
            log.warning(f"⚠️  Telegram chat discovery failed: {e}")
        return None
