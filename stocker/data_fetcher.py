"""Data fetcher — live price retrieval with rate-limit and market-hours handling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

import yfinance as yf

# NYSE/NASDAQ regular session in Eastern time
_MARKET_OPEN = dtime(9, 30)
_MARKET_CLOSE = dtime(16, 0)
_ET = ZoneInfo("America/New_York")


@dataclass
class PriceSnapshot:
    ticker: str
    price: float
    timestamp: datetime
    is_market_open: bool
    currency: str = "USD"


class BadTickerError(ValueError):
    pass


class MarketClosedError(RuntimeError):
    pass


class DataFetcher:
    def __init__(self, ticker: str, allow_extended: bool = True):
        self.ticker = ticker.upper()
        self.allow_extended = allow_extended
        self._yf_ticker: Optional[yf.Ticker] = None
        self._last_fetch: float = 0.0
        self._min_interval: float = 1.0   # never hit API faster than 1 s
        self._validate()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def fetch(self) -> PriceSnapshot:
        """Return the latest price snapshot, respecting rate limits."""
        self._throttle()
        price = self._get_price_with_retry()
        now = datetime.now(_ET)
        return PriceSnapshot(
            ticker=self.ticker,
            price=price,
            timestamp=now,
            is_market_open=self._market_is_open(now),
        )

    def is_market_open(self) -> bool:
        return self._market_is_open(datetime.now(_ET))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        try:
            t = yf.Ticker(self.ticker)
            info = t.info
            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                # Fast-path check failed; try a tiny history pull
                hist = t.history(period="1d")
                if hist.empty:
                    raise BadTickerError(f"No data found for ticker '{self.ticker}'")
        except Exception as exc:
            if isinstance(exc, BadTickerError):
                raise
            raise BadTickerError(f"Could not validate ticker '{self.ticker}': {exc}") from exc
        self._yf_ticker = t

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
        raise RuntimeError(f"Failed to fetch price after {retries} attempts: {last_exc}") from last_exc

    def _extract_price(self) -> float:
        assert self._yf_ticker is not None
        info = self._yf_ticker.info
        # Prefer real-time fields, fall back gracefully
        for key in ("currentPrice", "regularMarketPrice", "ask", "bid", "previousClose"):
            val = info.get(key)
            if val and isinstance(val, (int, float)) and val > 0:
                return float(val)
        # Last resort: latest close from 1-minute history
        hist = self._yf_ticker.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        raise RuntimeError("No usable price field returned by yfinance")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_fetch = time.monotonic()

    @staticmethod
    def _market_is_open(now: datetime) -> bool:
        if now.weekday() >= 5:   # Saturday / Sunday
            return False
        return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE
