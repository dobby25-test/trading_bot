"""
Bot configuration.
Set sensitive values using environment variables before running.
"""

import os


CONFIG = {
    # Binance API Keys
    # Get from: https://www.binance.com/en/my/settings/api-management
    "API_KEY": os.getenv("BINANCE_API_KEY", ""),
    "API_SECRET": os.getenv("BINANCE_API_SECRET", ""),

    # Trading Mode
    # PAPER_TRADING = True  -> simulate trades (safe)
    # PAPER_TRADING = False -> LIVE trading (real money)
    "PAPER_TRADING": True,

    # Trading Pairs
    "TRADING_PAIRS": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT"],

    # Timeframe options: 1m, 5m, 15m, 1h, 4h
    "TIMEFRAME": "5m",

    # Check interval (seconds)
    "CHECK_INTERVAL": 100,

    # Risk Management
    "RISK_PER_TRADE_PCT": 1.5,
    "STOP_LOSS_PCT": 2.0,
    "TAKE_PROFIT_PCT": 4.0,
    "MAX_DAILY_LOSS_PCT": 5.0,
    "MAX_OPEN_TRADES": 3,

    # Paper Trading Starting Balance
    "PAPER_BALANCE": 50.0,

    # RSI Settings
    "RSI_PERIOD": 14,
    "RSI_OVERSOLD": 35,
    "RSI_OVERBOUGHT": 65,

    # EMA Settings
    "EMA_FAST": 9,
    "EMA_SLOW": 21,

    # News Sentiment
    "NEWS_SENTIMENT_THRESHOLD": 0.3,
    "CRYPTOPANIC_TOKEN": os.getenv("CRYPTOPANIC_TOKEN", ""),

    # Telegram Alerts
    # Get bot token: message @BotFather on Telegram
    # Get chat ID: message @userinfobot on Telegram
    "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN", ""),  # Empty disables alerts
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
}
