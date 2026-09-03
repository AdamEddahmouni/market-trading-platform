"""
Stealth HTTP Client - Multi-layer HTTP client with browser impersonation.
Uses curl_cffi for Chrome impersonation when available,
falls back to requests with stealth headers otherwise.
"""

import time
import random
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from src.scrapers.stealth import StealthProfile, RequestDelayer, CookieJar
from src.config import STEALTH_CONFIG

# Try to import curl_cffi (optional dependency for browser impersonation)
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except ImportError:
    HAS_CURL = False

import requests


class StealthSession:
    """
    A stealth HTTP session that:
    1. Uses curl_cffi for browser TLS fingerprint impersonation (when available)
    2. Falls back to requests with randomized browser headers
    3. Rotates User-Agent and other headers per request
    4. Manages rate limiting per domain
    5. Maintains cookies across requests
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or STEALTH_CONFIG
        self.profile = StealthProfile()
        self.delayer = RequestDelayer(
            min_delay=self.config.get("min_delay", 0.5),
            max_delay=self.config.get("max_delay", 3.0)
        )
        self.cookie_jar = CookieJar()
        self._session = None
        self._requests_session = None
        self._init_sessions()

    def _init_sessions(self):
        """Initialize underlying HTTP sessions."""
        if HAS_CURL and self.config.get("browser_impersonate", True):
            self._session = curl_requests.Session()
            self._session.impersonate = self.config.get("impersonate_browser", "chrome124")

        self._requests_session = requests.Session()
        self._requests_session.headers.update({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        })

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        return urlparse(url).netloc

    def _rotate_profile(self):
        """Periodically rotate browser profile."""
        if random.random() < 0.1:  # 10% chance of rotation per request
            self.profile.rotate()

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Perform a stealth GET request with browser impersonation.
        Returns None on failure after max retries.
        """
        domain = self._get_domain(url)
        max_retries = self.config.get("max_retries", 3)
        last_error = None

        for attempt in range(max_retries):
            try:
                self._rotate_profile()
                self.delayer.wait(domain)

                headers = self.profile.get_headers(
                    content_type=kwargs.pop("content_type", "html"),
                    referer=kwargs.pop("referer", None)
                )

                # Add cookies if we have them
                cookie_header = self.cookie_jar.get_cookie_header(domain)
                if cookie_header:
                    headers["Cookie"] = cookie_header

                # Merge any additional kwargs headers
                extra_headers = kwargs.pop("headers", {})
                headers.update(extra_headers)

                # Try curl_cffi first if available
                if HAS_CURL and self.config.get("browser_impersonate", True):
                    response = self._session.get(
                        url,
                        headers=headers,
                        timeout=kwargs.pop("timeout", 30),
                        verify=self.config.get("verify_ssl", True),
                        **kwargs
                    )
                else:
                    response = self._requests_session.get(
                        url,
                        headers=headers,
                        timeout=kwargs.pop("timeout", 30),
                        verify=self.config.get("verify_ssl", True),
                        **kwargs
                    )

                # Update cookies from response
                if response.cookies:
                    self.cookie_jar.update(domain, dict(response.cookies))

                # Check for rate-limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    print(f"  [STEALTH] Rate limited on {domain}, waiting {retry_after}s...")
                    time.sleep(retry_after + random.uniform(1, 3))
                    continue

                if response.status_code == 403:
                    # Blocked - rotate profile and try again
                    self.profile.rotate()
                    print(f"  [STEALTH] 403 Forbidden on {domain}, rotating profile...")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(2, 5))
                        continue
                    return None

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                last_error = f"Timeout on {domain}"
                if attempt < max_retries - 1:
                    self.delayer.exponential_backoff(attempt)
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error on {domain}: {e}"
                if attempt < max_retries - 1:
                    self.delayer.exponential_backoff(attempt)
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP error on {domain}: {e}"
                # Don't retry 4xx errors except 429 and 403
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code in (404, 401, 400):
                        return None
                if attempt < max_retries - 1:
                    self.delayer.exponential_backoff(attempt)
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                if attempt < max_retries - 1:
                    self.delayer.exponential_backoff(attempt)

        print(f"  [STEALTH] Failed after {max_retries} retries: {last_error}")
        return None

    def post(self, url: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None, **kwargs) -> Optional[requests.Response]:
        """
        Perform a stealth POST request.
        """
        domain = self._get_domain(url)
        max_retries = self.config.get("max_retries", 3)

        for attempt in range(max_retries):
            try:
                self._rotate_profile()
                self.delayer.wait(domain)

                headers = self.profile.get_headers(
                    content_type=kwargs.pop("content_type", "api"),
                    referer=kwargs.pop("referer", None)
                )
                extra_headers = kwargs.pop("headers", {})
                headers.update(extra_headers)

                if HAS_CURL and self.config.get("browser_impersonate", True):
                    response = self._session.post(
                        url, data=data, json=json_data,
                        headers=headers,
                        timeout=kwargs.pop("timeout", 30),
                        verify=self.config.get("verify_ssl", True),
                        **kwargs
                    )
                else:
                    response = self._requests_session.post(
                        url, data=data, json=json_data,
                        headers=headers,
                        timeout=kwargs.pop("timeout", 30),
                        verify=self.config.get("verify_ssl", True),
                        **kwargs
                    )

                if response.status_code == 429:
                    time.sleep(5 + random.uniform(1, 3))
                    continue

                response.raise_for_status()
                return response

            except Exception as e:
                if attempt < max_retries - 1:
                    self.delayer.exponential_backoff(attempt)
                else:
                    print(f"  [STEALTH] POST failed: {e}")
                    return None

        return None

    def close(self):
        """Close underlying sessions."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        if self._requests_session:
            self._requests_session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
