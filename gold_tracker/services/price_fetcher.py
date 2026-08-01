"""Gold price fetching for live quotes and historical trend data."""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import pandas as pd
import requests
import yfinance as yf
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

from ..config import (
    APP_NAME,
    CACHE_DURATION_SECONDS,
    EGYPT_GRAPHQL_URL,
    EGYPT_UNIT_GRAMS,
    EGYPT_URL,
    FETCH_RETRY_ATTEMPTS,
    FETCH_RETRY_BACKOFF_SECONDS,
    HISTORY_DAYS,
    KEY_EGYPT,
    KEY_WORLDWIDE,
    REQUEST_TIMEOUT_SECONDS,
    STALE_CACHE_MAX_AGE_SECONDS,
    TROY_OUNCE_TO_GRAMS,
    WORLDWIDE_API_URL,
    WORLDWIDE_CURRENCY,
)
from ..models import HistoricalPriceSeries

logger = logging.getLogger(__name__)


class PriceFetchError(Exception):
    """Raised when a live or historical price source cannot be used."""


class UnexpectedSourceError(PriceFetchError):
    """Raised when a live source fails with an unexpected exception type."""


class GoldPriceFetcher:
    """Fetch live per-gram prices from the configured API and Egypt page."""

    def __init__(self):
        """Initialize the price fetcher."""
        self._cached_prices: dict[str, tuple[float, float]] = {}
        self._session = self._build_http_session()
        self._egypt_query_payload = self._build_egypt_query_payload(EGYPT_URL)
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
            allowed_methods=frozenset({"GET", "POST"}),
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

    def _record_warning(self, message: str) -> None:
        """Store a user-facing warning once per fetch cycle."""
        if message not in self.last_fetch_warnings:
            self.last_fetch_warnings.append(message)

    def _run_source_fetch(self, fetcher: Callable[[], float]) -> float:
        """Execute one source fetch and normalize unexpected failures."""
        try:
            return fetcher()
        except PriceFetchError:
            raise
        except Exception as exc:
            raise UnexpectedSourceError("Unexpected live source failure") from exc

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
        detail = (
            str(exc.__cause__) if unexpected and exc.__cause__ is not None else str(exc)
        )
        errors.append(f"{source_name}: {detail}")
        self._record_warning(f"{source_name} live feed unavailable")
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
        self._record_warning(f"{source_name} recent saved price active")
        logger.warning("Using stale cached %s gold price", source_name.lower())
        return stale_cache[source_key]

    def build_refresh_status(self, primary_feed: str) -> tuple[str, bool]:
        """Return a concise dashboard status message for the last live fetch."""
        warning_detail = ""
        if self.last_fetch_warnings:
            warning_detail = f" ({'; '.join(self.last_fetch_warnings)})"

        if self.last_fetch_used_stale_cache:
            return (
                (
                    "Warning: using recent saved prices while live feeds recover"
                    f"{warning_detail}"
                ),
                True,
            )

        if self.last_fetch_warnings:
            return (
                (
                    f"Warning: update completed with limited live data; using {primary_feed}"
                    f"{warning_detail}"
                ),
                True,
            )

        return (f"Prices updated - using {primary_feed}", False)

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
                    executor.submit(self._run_source_fetch, fetcher): (
                        source_key,
                        source_name,
                    )
                    for source_key, source_name, fetcher in missing_sources
                }

                for future in as_completed(future_to_source):
                    source_key, source_name = future_to_source[future]
                    try:
                        price = future.result()
                        prices[source_key] = price
                        self._update_cache(source_key, price)
                    except UnexpectedSourceError as exc:
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

        if not prices:
            if stale_cache is not None:
                self.last_fetch_used_stale_cache = True
                logger.warning("All sources failed; returning stale cached prices")
                return stale_cache
            raise PriceFetchError(f"Failed to fetch any prices: {'; '.join(errors)}")

        if errors:
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
        """Fetch the Egypt listing price from the Magento GraphQL endpoint."""
        last_error: Exception | None = None

        for attempt in range(1, FETCH_RETRY_ATTEMPTS + 1):
            try:
                response = self._session.post(
                    EGYPT_GRAPHQL_URL,
                    json=self._egypt_query_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                price = self._extract_egypt_price_from_graphql(response.json())

                if price <= 0:
                    raise PriceFetchError("Egypt source returned a non-positive price")

                return price / EGYPT_UNIT_GRAMS
            except (PriceFetchError, RequestException, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Egypt source attempt %s/%s failed: %s",
                    attempt,
                    FETCH_RETRY_ATTEMPTS,
                    exc,
                )
                if attempt < FETCH_RETRY_ATTEMPTS:
                    time.sleep(FETCH_RETRY_BACKOFF_SECONDS * attempt)

        raise PriceFetchError("Egypt source unavailable after retries") from last_error

    def _build_egypt_query_payload(self, product_url: str) -> dict[str, object]:
        """Build the GraphQL payload for the configured Egypt listing."""
        product_url_key = self._extract_product_url_key(product_url)
        return {
            "variables": {},
            "query": (
                "{"
                f' products(filter: {{url_key: {{eq: "{product_url_key}"}}}}) {{'
                " items {"
                " name"
                " sku"
                " price_range {"
                " maximum_price {"
                " final_price {"
                " value"
                " currency"
                " }"
                " }"
                " }"
                " }"
                " }"
                "}"
            ),
        }

    def _extract_product_url_key(self, product_url: str) -> str:
        """Return the Magento product URL key from the configured product URL."""
        path_parts = [part for part in urlparse(product_url).path.split("/") if part]
        if not path_parts:
            raise PriceFetchError("Egypt product URL is not configured correctly")

        return path_parts[-1]

    def _extract_egypt_price_from_graphql(self, payload: dict[str, object]) -> float:
        """Extract the configured listing price from a GraphQL response payload."""
        if payload.get("errors"):
            raise PriceFetchError("Egypt source returned GraphQL errors")

        try:
            items = payload["data"]["products"]["items"]
        except KeyError as exc:
            raise PriceFetchError("Egypt source returned unexpected data") from exc

        if not items:
            raise PriceFetchError("Egypt source returned no products")

        try:
            final_price = items[0]["price_range"]["maximum_price"]["final_price"]
            return float(final_price["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PriceFetchError("Egypt source returned an invalid price") from exc


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
        except (
            AttributeError,
            KeyError,
            RequestException,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
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
    import time

    print("Fetching gold prices...")
    try:
        start_time = time.perf_counter()
        prices = fetch_gold_prices()
        print("Gold price per gram (EGP):")
        if KEY_WORLDWIDE in prices:
            print(f"  Worldwide: {prices[KEY_WORLDWIDE]:,.2f}")
        if KEY_EGYPT in prices:
            print(f"  Egypt:     {prices[KEY_EGYPT]:,.2f}")
        end_time = time.perf_counter()
        fetched_duration = end_time - start_time
        print(f"Fetched in {fetched_duration:.2f} seconds")
    except PriceFetchError as e:
        print(f"Error: {e}")
