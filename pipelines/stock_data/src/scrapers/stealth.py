"""
Stealth Scraping Utilities - Browser fingerprint rotation, anti-detection,
and request camouflage for evading bot detection systems.
"""

import random
import string
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# ── Rotating User-Agent Pool ───────────────────────────────────
# Realistic, up-to-date user agent strings across major browsers

USER_AGENTS = [
    # Chrome 124 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 123 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome 124 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox 125 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Firefox 124 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox 125 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Edge 124 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Safari 17.4 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Chrome 124 on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 123 on macOS (alternate)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

# Platform-specific accept languages
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,es;q=0.8",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-CA,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.9,de;q=0.8",
    "en-US,en;q=0.9,zh-CN;q=0.8",
]

# Screen resolutions for Accept-CH header spoofing
SCREEN_RESOLUTIONS = [
    "1920x1080",
    "2560x1440",
    "1366x768",
    "1440x900",
    "1536x864",
    "1680x1050",
    "1920x1200",
    "1280x720",
]

# Common Accept headers
ACCEPT_HEADERS = {
    "html": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "json": "application/json, text/plain, */*",
    "api": "application/json, text/plain, */*",
}

# Referrer policies to rotate
REFERRER_POLICIES = [
    "strict-origin-when-cross-origin",
    "no-referrer-when-downgrade",
    "origin",
]


class StealthProfile:
    """
    Generates randomized browser profiles for request customization.
    Each profile looks like a unique real browser session.
    """

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or self._random_user_agent()
        self.accept_language = random.choice(ACCEPT_LANGUAGES)
        self.screen_resolution = random.choice(SCREEN_RESOLUTIONS)
        self.referrer_policy = random.choice(REFERRER_POLICIES)
        self.sec_ch_ua = self._generate_sec_ch_ua()
        self.session_id = self._random_session_id()

    def _random_user_agent(self) -> str:
        """Pick a random user agent from the pool."""
        return random.choice(USER_AGENTS)

    def _random_session_id(self) -> str:
        """Generate a random-looking session identifier."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

    def _generate_sec_ch_ua(self) -> str:
        """Generate a Sec-CH-UA header matching the user agent."""
        if "Chrome/124" in self.user_agent or "Edg/124" in self.user_agent:
            return '"Chromium";v="124", "Google Chrome";v="124", "Not=A?Brand";v="99"'
        elif "Chrome/123" in self.user_agent:
            return '"Chromium";v="123", "Google Chrome";v="123", "Not=A?Brand";v="99"'
        elif "Firefox/125" in self.user_agent:
            return '"Firefox";v="125", "Not=A?Brand";v="99"'
        else:
            return '"Chromium";v="124", "Google Chrome";v="124", "Not=A?Brand";v="99"'

    def get_headers(self, content_type: str = "html", referer: Optional[str] = None) -> Dict[str, str]:
        """
        Get a full set of browser-like headers for a request.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": ACCEPT_HEADERS.get(content_type, ACCEPT_HEADERS["html"]),
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document" if content_type == "html" else "empty",
            "Sec-Fetch-Mode": "navigate" if content_type == "html" else "cors",
            "Sec-Fetch-Site": "same-origin" if referer else "none",
            "Sec-Fetch-User": "?1" if content_type == "html" else None,
            "Upgrade-Insecure-Requests": "1" if content_type == "html" else None,
            "DNT": "1",
            "Connection": "keep-alive",
        }
        # Add Chrome-specific headers
        if "Chrome" in self.user_agent or "Edg" in self.user_agent:
            headers["Sec-Ch-Ua"] = self.sec_ch_ua
            headers["Sec-Ch-Ua-Mobile"] = "?0"
            headers["Sec-Ch-Ua-Platform"] = self._detect_platform()

        # Filter out None values
        return {k: v for k, v in headers.items() if v is not None}

    def _detect_platform(self) -> str:
        """Extract platform from user agent."""
        if "Windows" in self.user_agent:
            return '"Windows"'
        elif "Macintosh" in self.user_agent or "Mac OS" in self.user_agent:
            return '"macOS"'
        elif "Linux" in self.user_agent:
            return '"Linux"'
        return '"Windows"'

    def rotate(self):
        """Rotate to a new browser profile."""
        self.user_agent = self._random_user_agent()
        self.accept_language = random.choice(ACCEPT_LANGUAGES)
        self.screen_resolution = random.choice(SCREEN_RESOLUTIONS)
        self.sec_ch_ua = self._generate_sec_ch_ua()


class RequestDelayer:
    """
    Intelligent rate limiter that mimics human browsing patterns.
    Adds jitter and variable delays between requests to avoid
    triggering rate-limit detection.
    """

    def __init__(self, min_delay: float = 0.5, max_delay: float = 3.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request: Dict[str, float] = {}

    def wait(self, domain: str = "default"):
        """Wait appropriate amount before next request to domain."""
        import time
        now = time.time()
        last = self._last_request.get(domain, 0)
        elapsed = now - last

        # Add jitter: random delay between min and max
        delay = random.uniform(self.min_delay, self.max_delay)

        if elapsed < delay:
            wait_time = delay - elapsed
            time.sleep(wait_time)

        self._last_request[domain] = time.time()

    def exponential_backoff(self, attempt: int, base_delay: float = 1.0):
        """Wait with exponential backoff for retries."""
        import time
        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
        time.sleep(delay)


class CookieJar:
    """
    Manages cookies across requests to appear as a persistent browser session.
    """

    def __init__(self):
        self.cookies: Dict[str, Dict[str, str]] = {}
        self.session_cookies: Dict[str, str] = {}

    def update(self, domain: str, response_cookies: Dict[str, str]):
        """Update stored cookies for a domain."""
        if domain not in self.cookies:
            self.cookies[domain] = {}
        self.cookies[domain].update(response_cookies)

    def get_cookie_header(self, domain: str) -> Optional[str]:
        """Get Cookie header for a domain."""
        if domain in self.cookies and self.cookies[domain]:
            return "; ".join(
                f"{k}={v}" for k, v in self.cookies[domain].items()
            )
        return None

    def clear(self, domain: Optional[str] = None):
        """Clear cookies for a domain or all domains."""
        if domain:
            self.cookies.pop(domain, None)
        else:
            self.cookies.clear()


# Convenience function to get a fresh stealth session
def create_stealth_session() -> Tuple[StealthProfile, RequestDelayer, CookieJar]:
    """
    Create a complete stealth scraping session with profile, delayer, and cookie jar.
    """
    return StealthProfile(), RequestDelayer(), CookieJar()
