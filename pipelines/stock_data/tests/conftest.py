"""
Root pytest fixtures shared across all tests.

The most important one is `preserve_sigint_handler`, which ensures that any
test that installs a custom SIGINT handler restores the original before
returning. Without this, a test that monkey-patches the SIGINT handler could
break the pytest runner itself.
"""

from __future__ import annotations

import signal

import pytest


@pytest.fixture(autouse=True)
def preserve_sigint_handler(request):
    """Save and restore the SIGINT handler around every test.

    Tests that exercise signal handling will install their own handlers
    (BaseScraper does so for graceful Ctrl+C shutdown). We snapshot the
    pre-test handler and restore it after the test runs to keep the pytest
    process untouched.
    """
    # On Windows `signal.SIGINT` raises if there's no handler (ValueError on
    # some Python builds), so guard the snapshot defensively.
    try:
        original = signal.getsignal(signal.SIGINT)
    except (ValueError, OSError):
        original = None
    try:
        yield
    finally:
        if original is not None:
            try:
                signal.signal(signal.SIGINT, original)
            except (ValueError, OSError):
                pass
