"""
Trading Bot Dashboard
Run: python dashboard.py
"""

import json
import os
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer

TRADES_FILE = "logs/trades.json"
PORT = int(os.getenv("PORT", "8080"))


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def format_time(raw: str) -> str:
    if not raw:
        return "-"
    normalized = str(raw).replace("T", " ").split(".")[0]
    return normalized


def load_trades() -> dict:
    default = {"open": {}, "closed": []}
    if not os.path.exists(TRADES_FILE):
        return default

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default
            open_trades = data.get("open", {})
            closed_trades = data.get("closed", [])
            if not isinstance(open_trades, dict):
                open_trades = {}
            if not isinstance(closed_trades, list):
                closed_trades = []
            return {"open": open_trades, "closed": closed_trades}
    except (OSError, json.JSONDecodeError):
        return default


def normalize_closed_trade(trade: dict) -> dict:
    pair = str(trade.get("pair", "-"))
    direction = str(trade.get("direction", "-")).upper()
    entry = safe_float(trade.get("entry", 0.0))
    exit_price = safe_float(trade.get("exit", 0.0))
    pnl = safe_float(trade.get("pnl", 0.0))
    reason = str(trade.get("reason", "-"))
    result = str(trade.get("result", "-")).upper()
    close_time = str(trade.get("exit_time") or trade.get("time") or "")
    return {
        "pair": pair,
        "direction": direction,
        "entry": entry,
        "exit": exit_price,
        "pnl": pnl,
        "reason": reason,
        "result": result,
        "close_time": close_time,
    }


def get_stats(trades: dict) -> dict:
    closed = [normalize_closed_trade(t) for t in trades["closed"]]
    total = len(closed)
    wins = sum(1 for t in closed if t["result"] == "WIN")
    losses = total - wins
    total_pnl = sum(t["pnl"] for t in closed)
    best = max((t["pnl"] for t in closed), default=0.0)
    worst = min((t["pnl"] for t in closed), default=0.0)
    win_rate = (wins / total * 100.0) if total else 0.0
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 4),
        "win_rate": round(win_rate, 1),
        "best": round(best, 4),
        "worst": round(worst, 4),
        "open": len(trades["open"]),
    }


def build_open_rows(open_trades: dict) -> str:
    rows = []
    for pair, t in sorted(open_trades.items()):
        direction = str(t.get("direction", "-")).upper()
        badge = "green" if direction == "BUY" else "red"
        rows.append(
            f"""
        <tr>
            <td><span class="badge blue">{escape(str(pair))}</span></td>
            <td><span class="badge {badge}">{escape(direction)}</span></td>
            <td>{safe_float(t.get("entry", 0.0)):.4f}</td>
            <td class="red">{safe_float(t.get("sl", 0.0)):.4f}</td>
            <td class="green">{safe_float(t.get("tp", 0.0)):.4f}</td>
            <td>{safe_float(t.get("rsi", 0.0)):.1f}</td>
            <td>{escape(format_time(t.get("time", "")))}</td>
            <td><span class="badge yellow">OPEN</span></td>
        </tr>
        """
        )
    if not rows:
        return '<tr><td colspan="8" style="text-align:center;color:#7a828e">No open trades</td></tr>'
    return "".join(rows)


def build_closed_rows(closed_trades: list) -> str:
    normalized = [normalize_closed_trade(t) for t in closed_trades]
    normalized.sort(key=lambda t: t["close_time"], reverse=True)
    rows = []
    for t in normalized:
        pnl_class = "green" if t["pnl"] >= 0 else "red"
        result_badge = "green" if t["result"] == "WIN" else "red"
        direction_badge = "green" if t["direction"] == "BUY" else "red"
        rows.append(
            f"""
        <tr>
            <td><span class="badge blue">{escape(t["pair"])}</span></td>
            <td><span class="badge {direction_badge}">{escape(t["direction"])}</span></td>
            <td>{t["entry"]:.4f}</td>
            <td>{t["exit"]:.4f}</td>
            <td class="{pnl_class}">{t["pnl"]:+.4f} USDT</td>
            <td>{escape(t["reason"])}</td>
            <td>{escape(format_time(t["close_time"]))}</td>
            <td><span class="badge {result_badge}">{escape(t["result"])}</span></td>
        </tr>
        """
        )
    if not rows:
        return '<tr><td colspan="8" style="text-align:center;color:#7a828e">No closed trades in history yet</td></tr>'
    return "".join(rows)


def build_html() -> str:
    trades = load_trades()
    stats = get_stats(trades)
    open_rows = build_open_rows(trades["open"])
    closed_rows = build_closed_rows(trades["closed"])

    pnl_color = "#00c896" if stats["total_pnl"] >= 0 else "#ff4d6d"
    wr_color = "#00c896" if stats["win_rate"] >= 50 else "#ff4d6d"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="30">
<title>Trading Bot Dashboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: "Segoe UI", sans-serif; background:#0d1117; color:#e6edf3; min-height:100vh; }}
  header {{ background:#161b22; border-bottom:1px solid #30363d; padding:16px 24px; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }}
  header h1 {{ font-size:1.2rem; color:#58a6ff; }}
  .updated {{ font-size:0.78rem; color:#7a828e; }}
  .live {{ display:inline-block; width:8px; height:8px; background:#00c896; border-radius:50%; margin-right:6px; animation:pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.35}} }}
  .container {{ padding:24px; max-width:1300px; margin:0 auto; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; margin-bottom:28px; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:10px; padding:20px; text-align:center; }}
  .card .label {{ font-size:0.75rem; color:#8b949e; margin-bottom:8px; text-transform:uppercase; letter-spacing:1px; }}
  .card .value {{ font-size:1.8rem; font-weight:700; }}
  .green {{ color:#00c896; }}
  .red {{ color:#ff4d6d; }}
  .blue {{ color:#58a6ff; }}
  .yellow {{ color:#f0c040; }}
  section {{ background:#161b22; border:1px solid #30363d; border-radius:10px; margin-bottom:24px; overflow:auto; }}
  section h2 {{ padding:16px 20px; font-size:0.9rem; color:#8b949e; border-bottom:1px solid #30363d; text-transform:uppercase; letter-spacing:1px; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.85rem; min-width:960px; }}
  th {{ padding:10px 16px; text-align:left; color:#8b949e; font-weight:500; border-bottom:1px solid #21262d; }}
  td {{ padding:10px 16px; border-bottom:1px solid #21262d; }}
  tr:hover td {{ background:#1c2128; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }}
  .badge.green {{ background:#0d3d2b; color:#00c896; }}
  .badge.red {{ background:#3d0d1a; color:#ff4d6d; }}
  .badge.blue {{ background:#0d1f3d; color:#58a6ff; }}
  .badge.yellow {{ background:#3d3000; color:#f0c040; }}
</style>
</head>
<body>
<header>
  <h1><span class="live"></span>Trading Bot Dashboard</h1>
  <span class="updated">Auto-refresh 30s | Last updated: {now} | Log file: {TRADES_FILE}</span>
</header>
<div class="container">
  <div class="stats">
    <div class="card"><div class="label">Total P&L</div><div class="value" style="color:{pnl_color}">{stats['total_pnl']:+.2f}</div><div style="font-size:0.75rem;color:#7a828e;margin-top:4px">USDT</div></div>
    <div class="card"><div class="label">Win Rate</div><div class="value" style="color:{wr_color}">{stats['win_rate']:.1f}%</div><div style="font-size:0.75rem;color:#7a828e;margin-top:4px">{stats['wins']}W / {stats['losses']}L</div></div>
    <div class="card"><div class="label">Closed Trades</div><div class="value blue">{stats['total']}</div><div style="font-size:0.75rem;color:#7a828e;margin-top:4px">history count</div></div>
    <div class="card"><div class="label">Open Trades</div><div class="value yellow">{stats['open']}</div><div style="font-size:0.75rem;color:#7a828e;margin-top:4px">active now</div></div>
    <div class="card"><div class="label">Best Trade</div><div class="value green">{stats['best']:+.2f}</div><div style="font-size:0.75rem;color:#7a828e;margin-top:4px">USDT</div></div>
    <div class="card"><div class="label">Worst Trade</div><div class="value red">{stats['worst']:+.2f}</div><div style="font-size:0.75rem;color:#7a828e;margin-top:4px">USDT</div></div>
  </div>

  <section>
    <h2>Open Trades ({stats['open']})</h2>
    <table>
      <thead><tr><th>Pair</th><th>Direction</th><th>Entry</th><th>Stop Loss</th><th>Take Profit</th><th>RSI</th><th>Time</th><th>Status</th></tr></thead>
      <tbody>{open_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Trade P&amp;L History (All Closed Trades)</h2>
    <table>
      <thead><tr><th>Pair</th><th>Direction</th><th>Entry</th><th>Exit</th><th>P&amp;L</th><th>Reason</th><th>Closed Time</th><th>Result</th></tr></thead>
      <tbody>{closed_rows}</tbody>
    </table>
  </section>
</div>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        html = build_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    print(f"[Dashboard] Running at http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), DashboardHandler).serve_forever()
