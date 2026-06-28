"""Data fetcher — live price retrieval via Alpaca Markets API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

# NYSE/NASDAQ regular session in Eastern time
_MARKET_OPEN  = dtime(9, 30)
_MARKET_CLOSE = dtime(16, 0)
_ET = ZoneInfo("America/New_York")

# Coins supported by Alpaca's crypto feed
SUPPORTED_CRYPTO = [
    "BTC", "ETH", "SOL", "DOGE", "SHIB", "AVAX", "LTC", "BCH",
    "LINK", "UNI", "AAVE", "DOT", "MATIC", "ALGO", "BAT",
    "CRV", "SUSHI", "XTZ", "USDC", "USDT",
]


@dataclass
class PriceSnapshot:
    ticker: str
    price: float
    timestamp: datetime
    is_market_open: bool
    currency: str = "USD"
    mode: str = "stock"


class BadTickerError(ValueError):
    pass


class MarketClosedError(RuntimeError):
    pass


def normalize_crypto_ticker(ticker: str) -> str:
    """Return display-format crypto ticker (BTC -> BTC-USD, BTC/USD -> BTC-USD)."""
    ticker = ticker.upper()
    if "/" in ticker:
        return ticker.replace("/", "-")
    if "-" not in ticker:
        return f"{ticker}-USD"
    return ticker


def _alpaca_crypto_symbol(ticker: str) -> str:
    """Convert display ticker (BTC-USD) to Alpaca format (BTC/USD)."""
    ticker = ticker.upper()
    if "/" in ticker:
        return ticker
    if "-" in ticker:
        base, quote = ticker.split("-", 1)
        return f"{base}/{quote}"
    return f"{ticker}/USD"


class DataFetcher:
    def __init__(
        self,
        ticker: str,
        mode: str = "stock",
        api_key: str = "",
        api_secret: str = "",
    ):
        self.mode       = mode.lower()
        self.ticker     = (
            normalize_crypto_ticker(ticker) if self.mode == "crypto"
            else ticker.upper()
        )
        self._api_key    = api_key
        self._api_secret = api_secret
        self._last_fetch: float = 0.0
        self._min_interval: float = 1.0
        self._client     = self._build_client()
        self._validate()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def fetch(self) -> PriceSnapshot:
        self._throttle()
        price = self._get_price_with_retry()
        now   = datetime.now(_ET)
        open_ = True if self.mode == "crypto" else self._market_is_open(now)
        return PriceSnapshot(
            ticker=self.ticker,
            price=price,
            timestamp=now,
            is_market_open=open_,
            mode=self.mode,
        )

    def is_market_open(self) -> bool:
        if self.mode == "crypto":
            return True
        return self._market_is_open(datetime.now(_ET))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_client(self):
        pass  # clients are created fresh on each fetch to avoid stale cached data

    def _validate(self) -> None:
        try:
            self._extract_price()
        except Exception as exc:
            raise BadTickerError(
                f"Could not fetch price for '{self.ticker}': {exc}"
            ) from exc

    def _get_price_with_retry(self, retries: int = 4) -> float:
        delay = 2.0
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return self._extract_price()
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
        raise RuntimeError(
            f"Failed to fetch price after {retries} attempts: {last_exc}"
        ) from last_exc

    def _extract_price(self) -> float:
        if self.mode == "crypto":
            return self._fetch_crypto()
        return self._fetch_stock()

    def _fetch_stock(self) -> float:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
        client = StockHistoricalDataClient(self._api_key, self._api_secret)
        req    = StockLatestTradeRequest(symbol_or_symbols=self.ticker)
        trades = client.get_stock_latest_trade(req)
        trade  = trades.get(self.ticker)
        if not trade or not trade.price:
            raise RuntimeError(f"No trade data returned for {self.ticker}")
        return float(trade.price)

    def _fetch_crypto(self) -> float:
        from alpaca.data.historical import CryptoHistoricalDataClient
        from alpaca.data.requests import CryptoLatestTradeRequest
        client = CryptoHistoricalDataClient()
        symbol = _alpaca_crypto_symbol(self.ticker)
        req    = CryptoLatestTradeRequest(symbol_or_symbols=symbol)
        trades = client.get_crypto_latest_trade(req)
        trade  = trades.get(symbol)
        if not trade or not trade.price:
            raise RuntimeError(f"No trade data returned for {symbol}")
        return float(trade.price)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_fetch = time.monotonic()

    @staticmethod
    def _market_is_open(now: datetime) -> bool:
        if now.weekday() >= 5:
            return False
        return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE
