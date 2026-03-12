"""
Trade Executor — Places orders on Binance (or simulates in paper mode)
"""

import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import CONFIG

log = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self):
        self.paper_mode   = CONFIG["PAPER_TRADING"]
        self.paper_balance = CONFIG["PAPER_BALANCE"]
        self.client = Client(CONFIG["API_KEY"], CONFIG["API_SECRET"])

    def get_balance(self) -> float:
        """Get available USDT balance"""
        if self.paper_mode:
            return self.paper_balance

        try:
            info = self.client.get_asset_balance(asset="USDT")
            return float(info["free"])
        except Exception as e:
            log.error(f"❌ Balance fetch error: {e}")
            return 0.0

    def place_order(self, symbol: str, direction: str, qty: float, price: float) -> dict:
        """Place a market order (or simulate in paper mode)"""

        if self.paper_mode:
            return self._paper_order(symbol, direction, qty, price)

        try:
            side = Client.SIDE_BUY if direction == "BUY" else Client.SIDE_SELL
            order = self.client.order_market(
                symbol=symbol,
                side=side,
                quantity=qty
            )
            log.info(f"✅ Order placed: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            log.error(f"❌ Order failed: {e.message}")
            return {}
        except Exception as e:
            log.error(f"❌ Unexpected error placing order: {e}")
            return {}

    def _paper_order(self, symbol: str, direction: str, qty: float, price: float) -> dict:
        """Simulate order execution in paper trading mode"""
        cost = qty * price
        if direction == "BUY":
            if cost > self.paper_balance:
                log.warning(f"⚠️  Insufficient paper balance (${self.paper_balance:.2f} < ${cost:.2f})")
                return {}
            self.paper_balance -= cost
        else:
            self.paper_balance += cost

        log.info(f"📄 PAPER {direction}: {qty} {symbol} @ {price:.4f} | Balance: ${self.paper_balance:.2f}")
        return {
            "orderId": f"PAPER_{symbol}_{direction}_{int(price)}",
            "symbol":  symbol,
            "side":    direction,
            "qty":     qty,
            "price":   price,
        }