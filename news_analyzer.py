"""
News Analyzer — Fetches crypto news and scores sentiment
Uses free public RSS/API feeds + VADER NLP

Sources (in fallback order):
  1. CryptoCompare API      — coin-specific, JSON
  2. CoinTelegraph RSS      — coin-specific tag feed
  3. Bitcoinist RSS         — filtered by coin name
  4. NewsBTC RSS            — filtered by coin name
  5. CryptoSlate RSS        — filtered by coin name
  6. BeInCrypto RSS         — filtered by coin name
  7. Google News RSS        — coin-specific search
  8. Reddit RSS             — coin-specific search
"""

import requests
import logging
import re
import xml.etree.ElementTree as ET
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from config import CONFIG

log = logging.getLogger(__name__)

# Map trading symbol → full coin name (used for RSS tag/keyword searches)
COIN_NAMES = {
    "XAU":  "gold",
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "SOL":  "solana",
    "BNB":  "bnb",
    "XRP":  "ripple",
    "ADA":  "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche",
    "MATIC": "polygon",
    "DOT":  "polkadot",
    "LINK": "chainlink",
    "LTC":  "litecoin",
    "UNI":  "uniswap",
    "ATOM": "cosmos",
    "NEAR": "near-protocol",
}

class NewsAnalyzer:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.cache = {}
        self.cache_time = {}
        self.cp_token = CONFIG.get("CRYPTOPANIC_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

    def get_sentiment(self, coin: str) -> dict:
        """
        Fetch latest news for a coin and return sentiment score.
        Score: -1.0 (very negative) to +1.0 (very positive)
        """
        import time
        now = time.time()

        # Cache for 10 minutes
        if coin in self.cache and (now - self.cache_time.get(coin, 0)) < 600:
            return self.cache[coin]

        headlines = self._fetch_news(coin)
        if not headlines:
            return {"score": 0.0, "label": "NEUTRAL", "headlines": []}

        scores = [self.analyzer.polarity_scores(h)["compound"] for h in headlines]
        avg_score = sum(scores) / len(scores)

        label = "POSITIVE" if avg_score > 0.1 else "NEGATIVE" if avg_score < -0.1 else "NEUTRAL"
        result = {
            "score":     round(avg_score, 3),
            "label":     label,
            "headlines": headlines[:3],
        }

        self.cache[coin]      = result
        self.cache_time[coin] = now

        log.info(f"📰 {coin} news: {label} ({avg_score:.2f}) | Sample: '{headlines[0][:60]}...'")
        return result

    # ── Full name helper ──────────────────────────────────────────────────────
    def _coin_name(self, coin: str) -> str:
        """Return the full lowercase coin name for URL slugs, e.g. BTC → bitcoin."""
        return COIN_NAMES.get(coin.upper(), coin.lower())

    # ── Fetch with fallback chain ─────────────────────────────────────────────
    def _fetch_news(self, coin: str) -> list:
        """Try each source in order; return the first non-empty result."""
        fetchers = [
            self._fetch_cryptopanic,      # #1 — best quality, coin-specific
            self._fetch_cryptocompare,
            self._fetch_cointelegraph_rss,
            self._fetch_bitcoinist_rss,
            self._fetch_newsbtc_rss,
            self._fetch_cryptoslate_rss,
            self._fetch_beincrypto_rss,
            self._fetch_google_rss,
            self._fetch_reddit_rss,
        ]
        for fetcher in fetchers:
            try:
                headlines = fetcher(coin)
                if headlines:
                    log.info(f"📡 {coin} news from {fetcher.__name__.replace('_fetch_', '')}")
                    return headlines
            except Exception as e:
                log.warning(f"⚠️  {fetcher.__name__} failed for {coin}: {e}")
        return []

    # ── Source 0: CryptoPanic (best — coin-specific, curated) ──────────────────
    def _fetch_cryptopanic(self, coin: str) -> list:
        if not self.cp_token:
            return []
        try:
            url = (
                f"https://cryptopanic.com/api/free/v1/posts/"
                f"?auth_token={self.cp_token}"
                f"&currencies={coin}"
                f"&public=true"
                f"&kind=news"
            )
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                log.warning(f"⚠️  CryptoPanic status={r.status_code} for {coin}")
                return []
            results = r.json().get("results", [])
            if not isinstance(results, list):
                return []
            titles = [
                item.get("title", "").strip()
                for item in results[:15]
                if isinstance(item, dict) and item.get("title")
            ]
            return titles
        except Exception as e:
            log.warning(f"⚠️  CryptoPanic fetch failed for {coin}: {e}")
            return []

    # ── Source 1: CryptoCompare API ───────────────────────────────────────────
    def _fetch_cryptocompare(self, coin: str) -> list:
        try:
            url = (
                "https://min-api.cryptocompare.com/data/v2/news/"
                f"?categories={coin}&excludeCategories=Sponsored&lang=EN"
            )
            r = self.session.get(url, timeout=5)
            if r.status_code != 200:
                return []
            payload = r.json()
            if not isinstance(payload, dict):
                return []
            # Response on error: {"Response": "Error", "Message": "..."}
            if payload.get("Response") == "Error":
                log.warning(f"⚠️  CryptoCompare API error for {coin}: {payload.get('Message','')}")
                return []
            data = payload.get("Data", [])
            if not isinstance(data, list):
                return []
            return [
                item["title"].strip()
                for item in data[:10]
                if isinstance(item, dict) and item.get("title")
            ]
        except Exception as e:
            log.warning(f"⚠️  CryptoCompare fetch failed for {coin}: {e}")
            return []

    # ── Source 2: CoinTelegraph RSS (coin-specific tag) ───────────────────────
    def _fetch_cointelegraph_rss(self, coin: str) -> list:
        try:
            name = self._coin_name(coin)
            url = f"https://cointelegraph.com/rss/tag/{name}"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            return self._parse_rss_titles(r.text, coin)
        except Exception as e:
            log.warning(f"⚠️  CoinTelegraph RSS failed for {coin}: {e}")
            return []

    # ── Source 3: Bitcoinist RSS (filtered) ───────────────────────────────────
    def _fetch_bitcoinist_rss(self, coin: str) -> list:
        try:
            url = "https://bitcoinist.com/feed/"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            return self._parse_rss_titles(r.text, coin)
        except Exception as e:
            log.warning(f"⚠️  Bitcoinist RSS failed for {coin}: {e}")
            return []

    # ── Source 4: NewsBTC RSS (filtered) ─────────────────────────────────────
    def _fetch_newsbtc_rss(self, coin: str) -> list:
        try:
            url = "https://www.newsbtc.com/feed/"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            return self._parse_rss_titles(r.text, coin)
        except Exception as e:
            log.warning(f"⚠️  NewsBTC RSS failed for {coin}: {e}")
            return []

    # ── Source 5: CryptoSlate RSS (filtered) ─────────────────────────────────
    def _fetch_cryptoslate_rss(self, coin: str) -> list:
        try:
            url = "https://cryptoslate.com/feed/"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            return self._parse_rss_titles(r.text, coin)
        except Exception as e:
            log.warning(f"⚠️  CryptoSlate RSS failed for {coin}: {e}")
            return []

    # ── Source 6: BeInCrypto RSS (filtered) ──────────────────────────────────
    def _fetch_beincrypto_rss(self, coin: str) -> list:
        try:
            url = "https://beincrypto.com/feed/"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            return self._parse_rss_titles(r.text, coin)
        except Exception as e:
            log.warning(f"⚠️  BeInCrypto RSS failed for {coin}: {e}")
            return []

    # ── Source 7: Google News RSS ─────────────────────────────────────────────
    def _fetch_google_rss(self, coin: str) -> list:
        try:
            name = self._coin_name(coin)
            query = f"{coin}+{name}+crypto"
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            titles = self._parse_rss_titles(r.text)  # No coin filter — query does it
            return [t for t in titles if not t.lower().startswith("google news")]
        except Exception as e:
            log.warning(f"⚠️  Google RSS failed for {coin}: {e}")
            return []

    # ── Source 8: Reddit RSS ──────────────────────────────────────────────────
    def _fetch_reddit_rss(self, coin: str) -> list:
        try:
            name = self._coin_name(coin)
            url = f"https://www.reddit.com/search.rss?q={coin}+{name}+crypto&sort=new"
            r = self.session.get(url, timeout=6)
            if r.status_code != 200:
                return []
            matches = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text, re.DOTALL)
            if not matches:
                matches = re.findall(r"<title>(.*?)</title>", r.text, re.DOTALL)
            return [m.strip() for m in matches[1:11]]
        except Exception:
            return []

    # ── Shared XML parser ─────────────────────────────────────────────────────
    def _parse_rss_titles(self, xml_text: str, coin_filter: str = None) -> list:
        """
        Parse <title> tags from an RSS/Atom feed.
        If coin_filter is set, only return headlines mentioning that coin
        symbol OR its full name (so e.g. 'bitcoin' matches for BTC).
        Works without lxml — strips namespaces before parsing.
        """
        titles = []
        try:
            # Remove XML namespaces so we can use simple tag names
            clean = re.sub(r'\sxmlns(?::[a-zA-Z0-9_]+)?="[^"]*"', '', xml_text)
            clean = re.sub(r'<([a-zA-Z0-9_]+):([a-zA-Z0-9_]+)', r'<\2', clean)
            clean = re.sub(r'</([a-zA-Z0-9_]+):([a-zA-Z0-9_]+)', r'</\2', clean)
            root = ET.fromstring(clean)
            for item in root.findall(".//item"):
                el = item.find("title")
                if el is not None:
                    t = (el.text or "").strip()
                    if t:
                        titles.append(t)
        except ET.ParseError:
            # Fallback: regex scrape when XML is malformed/too deeply nested
            raw = re.findall(
                r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
                xml_text, re.DOTALL
            )
            titles = [t.strip() for t in raw if t.strip()]

        # Apply coin-specific filter for general feeds
        if coin_filter:
            symbol = coin_filter.upper()
            name = self._coin_name(coin_filter).lower()
            filtered = [
                t for t in titles
                if symbol in t.upper() or name in t.lower()
            ]
            # Only return filtered results if we found enough; else fallback to all
            titles = filtered if len(filtered) >= 2 else []

        return titles[:10]
