"""
Data Fetcher — Gets price data from Binance
"""

import pandas as pd
import logging
from binance.client import Client
from config import CONFIG

log = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        self.client = Client(CONFIG["API_KEY"], CONFIG["API_SECRET"])

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV candlestick data from Binance"""
        try:
            interval_map = {
                "1m":  Client.KLINE_INTERVAL_1MINUTE,
                "5m":  Client.KLINE_INTERVAL_5MINUTE,
                "15m": Client.KLINE_INTERVAL_15MINUTE,
                "1h":  Client.KLINE_INTERVAL_1HOUR,
                "4h":  Client.KLINE_INTERVAL_4HOUR,
            }
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval_map.get(interval, Client.KLINE_INTERVAL_15MINUTE),
                limit=limit
            )
            df = pd.DataFrame(klines, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_vol", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df["close"]  = df["close"].astype(float)
            df["open"]   = df["open"].astype(float)
            df["high"]   = df["high"].astype(float)
            df["low"]    = df["low"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df
        except Exception as e:
            log.error(f"❌ Failed to fetch data for {symbol}: {e}")
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """Get latest price for a symbol"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            log.error(f"❌ Price fetch error: {e}")
            return 0.0