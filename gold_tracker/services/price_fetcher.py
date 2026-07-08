"""Gold price fetching for live quotes and historical trend data."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
import re
import time

import requests
import pandas as pd
import yfinance as yf
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.util.retry import Retry
from webdriver_manager.chrome import ChromeDriverManager

from ..config import (
    APP_NAME,
    EGYPT_URL,
    EGYPT_UNIT_GRAMS,
    CHROME_DRIVER_PATH,
    WORLDWIDE_API_URL,
    WORLDWIDE_CURRENCY,
    PAGE_LOAD_TIMEOUT_SECONDS,
    MIN_VALID_PRICE,
    CACHE_DURATION_SECONDS,
    FETCH_RETRY_ATTEMPTS,
    FETCH_RETRY_BACKOFF_SECONDS,
    KEY_WORLDWIDE,
    KEY_EGYPT,
    REQUEST_TIMEOUT_SECONDS,
    SELENIUM_WAIT_TIMEOUT_SECONDS,
    STALE_CACHE_MAX_AGE_SECONDS,
    TROY_OUNCE_TO_GRAMS,
    HISTORY_DAYS,
)
from ..models import HistoricalPriceSeries


logger = logging.getLogger(__name__)
_RESOLVED_CHROME_DRIVER_PATH: str | None = None


class PriceFetchError(Exception):
    """Raised when a live or historical price source cannot be used."""


class GoldPriceFetcher:
    """Fetch live per-gram prices from the configured API and Egypt page."""

    def __init__(self):
        """Initialize the price fetcher."""
        self._cached_prices: dict[str, tuple[float, float]] = {}
        self._chrome_driver_path: str | None = None
        self._session = self._build_http_session()
        self.last_fetch_warnings: list[str] = []
        self.last_fetch_used_stale_cache = False

    def close(self) -> None:
        """Close network resources held by the fetcher."""
        self._session.close()

    def _build_http_session(self) -> requests.Session:
        """Create an HTTP session with retry-enabled adapters."""
        retry_count = max(FETCH_RETRY_ATTEMPTS - 1, 0)
        retry_policy = Retry(
            total=retry_count,
            connect=retry_count,
            read=retry_count,
            status=retry_count,
            backoff_factor=FETCH_RETRY_BACKOFF_SECONDS,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        session = requests.Session()
        session.headers.update({"User-Agent": f"{APP_NAME}/1.0"})
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_cached_prices(self, max_age_seconds: int) -> dict[str, float] | None:
        """Return a copy of cached prices if they are not older than max_age_seconds."""
        if not self._cached_prices:
            return None

        now = time.time()
        fresh_prices = {
            source_key: price
            for source_key, (price, timestamp) in self._cached_prices.items()
            if now - timestamp <= max_age_seconds
        }
        if fresh_prices:
            return fresh_prices

        return None

    def _update_cache(self, source_key: str, price: float) -> None:
        """Store the latest successful price for one source."""
        self._cached_prices[source_key] = (price, time.time())

    def _handle_source_failure(
        self,
        source_key: str,
        source_name: str,
        exc: Exception,
        stale_cache: dict[str, float] | None,
        errors: list[str],
        unexpected: bool = False,
    ) -> float | None:
        """Record one failed source and use stale cache for that source if available."""
        errors.append(f"{source_name}: {exc}")
        if unexpected:
            logger.exception(
                "Unexpected error while fetching %s gold price",
                source_name.lower(),
            )
        else:
            logger.warning(
                "Failed to fetch %s gold price: %s",
                source_name.lower(),
                exc,
            )

        if stale_cache and source_key in stale_cache:
            # Fall back per source so a cached local price can still pair with a fresh global price.
            return self._cached_fallback(source_key, source_name, stale_cache)

        return None

    def _cached_fallback(
        self,
        source_key: str,
        source_name: str,
        stale_cache: dict[str, float],
    ) -> float:
        """Mark a source as served from stale cache."""
        self.last_fetch_used_stale_cache = True
        self.last_fetch_warnings.append(f"{source_name} cache fallback")
        logger.warning("Using stale cached %s gold price", source_name.lower())
        return stale_cache[source_key]

    def fetch(self, force_refresh: bool = False) -> dict[str, float]:
        """
        Fetch available EGP-per-gram prices from the configured live sources.

        A complete fresh cache is returned without network work unless
        ``force_refresh`` is true. If one source fails, the result may contain
        the other fresh source and, when available, a short-lived stale cached
        value for the failed source.

        Raises:
            PriceFetchError: If no live or stale source price can be returned.
        """
        self.last_fetch_warnings = []
        self.last_fetch_used_stale_cache = False

        sources = (
            (KEY_WORLDWIDE, "Worldwide", self._fetch_worldwide_price),
            (KEY_EGYPT, "Egypt", self._fetch_egypt_price),
        )

        if not force_refresh:
            fresh_cache = self._get_cached_prices(CACHE_DURATION_SECONDS)
            if fresh_cache is not None and len(fresh_cache) == len(sources):
                logger.info("Returning fresh cached gold prices")
                return fresh_cache
        else:
            fresh_cache = None

        prices: dict[str, float] = dict(fresh_cache or {})
        errors: list[str] = []
        # Keep a short-lived backup snapshot so transient source failures do not blank the UI.
        stale_cache = self._get_cached_prices(STALE_CACHE_MAX_AGE_SECONDS)

        missing_sources = [source for source in sources if source[0] not in prices]
        if missing_sources:
            with ThreadPoolExecutor(max_workers=len(missing_sources)) as executor:
                future_to_source = {
                    executor.submit(fetcher): (source_key, source_name)
                    for source_key, source_name, fetcher in missing_sources
                }

                for future in as_completed(future_to_source):
                    source_key, source_name = future_to_source[future]
                    try:
                        price = future.result()
                        prices[source_key] = price
                        self._update_cache(source_key, price)
                    except PriceFetchError as exc:
                        fallback_price = self._handle_source_failure(
                            source_key,
                            source_name,
                            exc,
                            stale_cache,
                            errors,
                        )
                        if fallback_price is not None:
                            prices[source_key] = fallback_price
                    except Exception as exc:
                        fallback_price = self._handle_source_failure(
                            source_key,
                            source_name,
                            exc,
                            stale_cache,
                            errors,
                            unexpected=True,
                        )
                        if fallback_price is not None:
                            prices[source_key] = fallback_price

        if not prices:
            if stale_cache is not None:
                self.last_fetch_used_stale_cache = True
                self.last_fetch_warnings.append("All sources served from stale cache")
                logger.warning("All sources failed; returning stale cached prices")
                return stale_cache
            raise PriceFetchError(f"Failed to fetch any prices: {'; '.join(errors)}")

        if errors:
            self.last_fetch_warnings.append("Partial source failure")
            logger.warning("Returning degraded gold price data: %s", "; ".join(errors))

        logger.info(
            "Fetched gold prices successfully (stale_cache=%s)",
            self.last_fetch_used_stale_cache,
        )

        return dict(prices)

    def _fetch_worldwide_price(self) -> float:
        """Fetch the API's EGP-per-gram worldwide price."""
        try:
            response = self._session.get(
                WORLDWIDE_API_URL,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            price_per_gram = float(data[WORLDWIDE_CURRENCY]["gram"])
        except RequestException as exc:
            raise PriceFetchError("Worldwide source is unavailable") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise PriceFetchError("Worldwide source returned unexpected data") from exc

        if price_per_gram <= 0:
            raise PriceFetchError("Worldwide source returned a non-positive price")

        return price_per_gram

    def _fetch_egypt_price(self) -> float:
        """Scrape the Egypt listing price and convert it to EGP per gram."""
        last_error: Exception | None = None

        for attempt in range(1, FETCH_RETRY_ATTEMPTS + 1):
            driver = None
            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                service = Service(self._get_chrome_driver_path())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
                driver.get(EGYPT_URL)

                price = WebDriverWait(driver, SELENIUM_WAIT_TIMEOUT_SECONDS).until(
                    self._wait_for_price_in_page_source
                )

                if price <= 0:
                    raise PriceFetchError("Egypt source returned a non-positive price")

                return price / EGYPT_UNIT_GRAMS
            except (
                PriceFetchError,
                RequestException,
                TimeoutException,
                WebDriverException,
            ) as exc:
                last_error = exc
                logger.warning(
                    "Egypt source attempt %s/%s failed: %s",
                    attempt,
                    FETCH_RETRY_ATTEMPTS,
                    exc,
                )
                if attempt < FETCH_RETRY_ATTEMPTS:
                    time.sleep(FETCH_RETRY_BACKOFF_SECONDS * attempt)
            finally:
                if driver:
                    driver.quit()

        raise PriceFetchError("Egypt source unavailable after retries") from last_error

    def _get_chrome_driver_path(self) -> str:
        """Resolve and cache the ChromeDriver executable path."""
        global _RESOLVED_CHROME_DRIVER_PATH

        if self._chrome_driver_path is None:
            configured_path = CHROME_DRIVER_PATH or os.getenv(
                "GOLDTRACKER_CHROMEDRIVER", ""
            )
            if configured_path:
                self._chrome_driver_path = configured_path
            elif _RESOLVED_CHROME_DRIVER_PATH is not None:
                self._chrome_driver_path = _RESOLVED_CHROME_DRIVER_PATH
            else:
                self._chrome_driver_path = ChromeDriverManager().install()
                _RESOLVED_CHROME_DRIVER_PATH = self._chrome_driver_path
        return self._chrome_driver_path

    def _wait_for_price_in_page_source(self, driver: webdriver.Chrome) -> float | bool:
        """Return the parsed price when it becomes available in the page source."""
        price = self._extract_price_from_html(driver.page_source)
        return price if price is not None else False

    def _extract_price_from_html(self, html: str) -> float | None:
        """Return the first realistic price candidate found in page HTML."""
        matches = self._extract_structured_price_candidates(html)
        if not matches:
            # Fall back to visible currency text with optional thousands separators.
            matches = re.findall(
                r"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?:EGP|ج\.م|جنيه)",
                html,
            )

        if not matches:
            return None

        # Filter to get realistic prices (should be large numbers for gold)
        for match in matches:
            clean = match.replace(",", "")
            try:
                val = float(clean)
                if val > MIN_VALID_PRICE:
                    return val
            except ValueError:
                continue

        return None

    def _extract_structured_price_candidates(self, html: str) -> list[str]:
        """Extract likely product-price values from structured page fragments."""
        matches = self._extract_json_ld_price_candidates(html)
        patterns = (
            r'"price"\s*:\s*"?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"?',
            r'data-price\s*=\s*"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"',
            r'itemprop\s*=\s*"price"[^>]*content\s*=\s*"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"',
        )
        for pattern in patterns:
            matches.extend(re.findall(pattern, html, flags=re.IGNORECASE))
        return matches

    def _extract_json_ld_price_candidates(self, html: str) -> list[str]:
        """Extract product offer prices from JSON-LD script blocks."""
        candidates: list[str] = []
        script_blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        for script_block in script_blocks:
            try:
                data = json.loads(script_block.strip())
            except json.JSONDecodeError:
                continue
            candidates.extend(self._walk_json_prices(data))

        return candidates

    def _walk_json_prices(self, value) -> list[str]:
        """Walk decoded JSON and collect values stored under price keys."""
        prices: list[str] = []
        if isinstance(value, dict):
            if "price" in value:
                prices.append(str(value["price"]))
            for nested_value in value.values():
                prices.extend(self._walk_json_prices(nested_value))
        elif isinstance(value, list):
            for item in value:
                prices.extend(self._walk_json_prices(item))
        return prices


def fetch_gold_prices() -> dict[str, float]:
    """Fetch current EGP-per-gram prices with a short-lived fetcher instance."""
    fetcher = GoldPriceFetcher()
    try:
        return fetcher.fetch()
    finally:
        fetcher.close()


def fetch_historical_prices(days: int = HISTORY_DAYS) -> HistoricalPriceSeries:
    """Load recent GC=F closes and convert them to a USD-per-gram series."""
    if days <= 0:
        raise PriceFetchError("History days must be a positive integer")

    last_error: Exception | None = None

    for attempt in range(1, FETCH_RETRY_ATTEMPTS + 1):
        try:
            end_date = pd.Timestamp.today()
            start_date = end_date - pd.DateOffset(days=days)

            gold_data = yf.download(
                "GC=F",
                start=start_date,
                end=end_date,
                interval="1d",
                progress=False,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if gold_data.empty:
                raise PriceFetchError("No historical data returned")

            try:
                close_data = gold_data["Close"]
            except KeyError as exc:
                raise PriceFetchError("Historical data missing close prices") from exc

            # yfinance can return either a symbol-keyed frame or a plain Close series.
            if isinstance(close_data, pd.DataFrame):
                if "GC=F" in close_data.columns:
                    price_series = close_data["GC=F"]
                elif close_data.shape[1] == 1:
                    price_series = close_data.iloc[:, 0]
                else:
                    raise PriceFetchError(
                        "Historical data returned ambiguous close prices"
                    )
            else:
                price_series = close_data

            price_series = price_series.dropna()
            dates = price_series.index.tolist()
            prices = (price_series / TROY_OUNCE_TO_GRAMS).astype(float).tolist()

            if not prices:
                raise PriceFetchError("Historical data returned no prices")

            logger.info("Fetched %s days of historical gold prices", days)
            return HistoricalPriceSeries(
                dates=dates,
                prices=prices,
                unit_label="USD/gram",
                source_label="Yahoo Finance (GC=F)",
                title="Gold",
            )
        except PriceFetchError as exc:
            last_error = exc
            logger.warning(
                "Historical fetch attempt %s/%s failed: %s",
                attempt,
                FETCH_RETRY_ATTEMPTS,
                exc,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Historical fetch attempt %s/%s failed: %s",
                attempt,
                FETCH_RETRY_ATTEMPTS,
                exc,
            )

        if attempt < FETCH_RETRY_ATTEMPTS:
            time.sleep(FETCH_RETRY_BACKOFF_SECONDS * attempt)

    raise PriceFetchError(
        f"Failed to fetch historical prices: {last_error}"
    ) from last_error


# =============================================================================
# For testing the module directly
# =============================================================================

if __name__ == "__main__":
    print("Fetching gold prices...")
    try:
        prices = fetch_gold_prices()
        print("Gold price per gram (EGP):")
        if KEY_WORLDWIDE in prices:
            print(f"  Worldwide: {prices[KEY_WORLDWIDE]:,.2f}")
        if KEY_EGYPT in prices:
            print(f"  Egypt:     {prices[KEY_EGYPT]:,.2f}")
    except PriceFetchError as e:
        print(f"Error: {e}")
