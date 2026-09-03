"""Centralized Finviz Elite credential ownership and recovery."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .auth_classification import FinvizFailureKind, classify_http_response
from .auth_state import FinvizAuthState, FinvizCredentialSource, FinvizRecoveryMode
from .config import (
    DEFAULT_SCREENER_COLUMNS,
    FINVIZ_EXPORT_URL,
    FINVIZ_EXPORT_VERSION,
    provider_env_path,
    _read_env_file,
)
from .http_client import urllib_get
from .login_recovery import LoginRecoveryStatus, recover_token_via_login
from .secure_store import (
    FinvizCredentialMetadata,
    clear_login_credentials,
    clear_secure_token,
    load_metadata,
    read_login_credentials,
    read_secure_token,
    record_credential_activation,
    save_metadata,
    write_secure_token,
)

RECOVERY_COOLDOWN_S = 300.0
MAX_RECOVERY_ATTEMPTS_PER_WINDOW = 2


def _env_override_token() -> str | None:
    for key in ("FINVIZ_API_KEY", "FINVIZ_AUTH_TOKEN", "FINVIZ_API_TOKEN"):
        value = os.environ.get(key)
        if value and value not in ("CHANGEME", ""):
            return value
    return None


def _provider_env_token() -> str | None:
    path = provider_env_path()
    if path is None:
        return None
    values = _read_env_file(path)
    token = values.get("FINVIZ_API_KEY") or values.get("FINVIZ_AUTH_TOKEN")
    if token and token not in ("CHANGEME", ""):
        return token
    return None


def read_login_credentials_from_env() -> tuple[str | None, str | None]:
    path = provider_env_path()
    if path is None:
        return None, None
    values = _read_env_file(path)
    username = values.get("FINVIZ_USERNAME") or None
    password = values.get("FINVIZ_PASSWORD") or None
    return username, password


def _configured_token_with_source() -> tuple[str | None, FinvizCredentialSource]:
    env_token = _env_override_token()
    if env_token:
        return env_token, FinvizCredentialSource.ENVIRONMENT
    secure = read_secure_token()
    if secure:
        return secure, FinvizCredentialSource.PRIVATE_FILE
    file_token = _provider_env_token()
    if file_token:
        return file_token, FinvizCredentialSource.PROVIDER_ENV_FILE
    return None, FinvizCredentialSource.NONE


@dataclass
class FinvizAuthHealth:
    state: FinvizAuthState
    source: FinvizCredentialSource
    credential_present: bool
    finviz_credential_generation: int
    last_validated: str | None
    last_rotation: str | None
    recovery_mode: FinvizRecoveryMode
    last_auth_error: str | None = None
    automatic_recovery: str = "UNAVAILABLE"


class FinvizCredentialManager:
    """Single owner for Finviz API credentials — load, validate, recover, swap."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._recovery_lock = threading.Lock()
        self._token: str | None = None
        self._source = FinvizCredentialSource.NONE
        self._state = FinvizAuthState.UNCONFIGURED
        self._metadata = load_metadata()
        self._last_auth_error: str | None = None
        self._recovery_attempts = 0
        self._recovery_window_start = 0.0
        self._http_getter: Callable[..., Any] | None = None

    def set_http_getter(self, getter: Callable[..., Any]) -> None:
        self._http_getter = getter

    def load(self) -> str | None:
        with self._lock:
            token, source = _configured_token_with_source()
            if token:
                self._token = token
                self._source = source
                self._state = FinvizAuthState.LOADED
                return self._token
            self._token = None
            self._source = FinvizCredentialSource.NONE
            self._state = FinvizAuthState.UNCONFIGURED
            return None

    def get_token(self) -> str | None:
        with self._lock:
            if self._token is None:
                self.load()
            return self._token

    def configured(self) -> bool:
        return bool(self.get_token())

    def health(self) -> FinvizAuthHealth:
        with self._lock:
            recovery_mode = self._recovery_mode_unlocked()
            return FinvizAuthHealth(
                state=self._state,
                source=self._source,
                credential_present=bool(self._token),
                finviz_credential_generation=self._metadata.finviz_credential_generation,
                last_validated=self._metadata.last_validated,
                last_rotation=self._metadata.last_rotation,
                recovery_mode=recovery_mode,
                last_auth_error=self._last_auth_error,
                automatic_recovery=self._automatic_recovery_label(recovery_mode),
            )

    def _recovery_mode_unlocked(self) -> FinvizRecoveryMode:
        if self._source == FinvizCredentialSource.ENVIRONMENT:
            return FinvizRecoveryMode.MANUAL
        if self._source not in (FinvizCredentialSource.NONE,):
            return FinvizRecoveryMode.AUTO
        username, password = read_login_credentials()
        if not username or not password:
            username, password = read_login_credentials_from_env()
        if username and password:
            return FinvizRecoveryMode.LOGIN_REQUIRED
        return FinvizRecoveryMode.MANUAL

    def _automatic_recovery_label(self, mode: FinvizRecoveryMode) -> str:
        if mode == FinvizRecoveryMode.AUTO:
            return "AUTOMATIC"
        if mode == FinvizRecoveryMode.LOGIN_REQUIRED:
            return "PARTIAL"
        if mode == FinvizRecoveryMode.MANUAL:
            return "MANUAL"
        return "UNAVAILABLE"

    def validate_token(self, token: str, *, http_get: Callable[..., Any] | None = None) -> bool:
        getter = http_get or self._http_getter
        if getter is None:
            getter = urllib_get
        params = {
            "v": FINVIZ_EXPORT_VERSION,
            "f": "sh_float_u50",
            "c": DEFAULT_SCREENER_COLUMNS,
            "auth": token,
        }
        with self._lock:
            self._state = FinvizAuthState.VALIDATING
        try:
            response = getter(
                FINVIZ_EXPORT_URL,
                params=params,
                timeout=15,
                headers={"User-Agent": "IMP integrated-market-platform"},
            )
            status = int(getattr(response, "status_code", 0))
            body = getattr(response, "text", "") or ""
            content_type = str(getattr(response, "headers", {}).get("content-type", ""))
            classification = classify_http_response(
                status_code=status,
                body=body,
                content_type=content_type,
            )
            ok = classification.kind == FinvizFailureKind.AUTH_OK and "Ticker" in body
            with self._lock:
                if ok:
                    self._state = FinvizAuthState.HEALTHY
                    self._last_auth_error = None
                else:
                    self._state = self._state_from_kind(classification.kind)
                    self._last_auth_error = classification.kind.value
            return ok
        except Exception:
            with self._lock:
                self._state = FinvizAuthState.ERROR
                self._last_auth_error = "NETWORK_ERROR"
            return False

    def _state_from_kind(self, kind: FinvizFailureKind) -> FinvizAuthState:
        mapping = {
            FinvizFailureKind.AUTH_INVALID: FinvizAuthState.AUTH_INVALID,
            FinvizFailureKind.AUTH_EXPIRED: FinvizAuthState.AUTH_EXPIRED,
            FinvizFailureKind.AUTH_REVOKED: FinvizAuthState.AUTH_REVOKED,
            FinvizFailureKind.RATE_LIMITED: FinvizAuthState.RATE_LIMITED,
            FinvizFailureKind.PROVIDER_ERROR: FinvizAuthState.PROVIDER_UNAVAILABLE,
            FinvizFailureKind.NETWORK_ERROR: FinvizAuthState.ERROR,
            FinvizFailureKind.SUBSCRIPTION_NOT_ELITE: FinvizAuthState.AUTH_OPERATOR_ACTION_REQUIRED,
        }
        return mapping.get(kind, FinvizAuthState.ERROR)

    def configure_token(self, token: str, *, validate: bool = True) -> bool:
        if validate and not self.validate_token(token):
            return False
        if self._source != FinvizCredentialSource.ENVIRONMENT:
            if not write_secure_token(token):
                return False
        with self._lock:
            rotated = self._token is not None and self._token != token
            self._token = token
            if self._source == FinvizCredentialSource.NONE:
                self._source = FinvizCredentialSource.PRIVATE_FILE
            self._state = FinvizAuthState.HEALTHY
            self._metadata = record_credential_activation(
                source=self._source.value,
                rotated=rotated,
            )
        return True

    def clear_credentials(self) -> None:
        with self._lock:
            if self._source != FinvizCredentialSource.ENVIRONMENT:
                clear_secure_token()
                clear_login_credentials()
            self._token = None
            self._source = FinvizCredentialSource.NONE
            self._state = FinvizAuthState.UNCONFIGURED
            self._metadata = FinvizCredentialMetadata()
            save_metadata(self._metadata)

    def classify_response(
        self,
        *,
        status_code: int,
        body: str = "",
        content_type: str = "",
        network_error: bool = False,
    ):
        return classify_http_response(
            status_code=status_code,
            body=body,
            content_type=content_type,
            network_error=network_error,
        )

    def should_attempt_recovery(self, classification) -> bool:
        if not classification.triggers_recovery:
            return False
        if self._source == FinvizCredentialSource.ENVIRONMENT:
            return False
        if classification.detail == "manual_auth_required":
            return False
        return True

    def attempt_recovery(self) -> bool:
        acquired = self._recovery_lock.acquire(blocking=False)
        if not acquired:
            deadline = time.monotonic() + 60.0
            while time.monotonic() < deadline:
                with self._lock:
                    if self._state == FinvizAuthState.HEALTHY:
                        return True
                time.sleep(0.1)
            with self._lock:
                return self._state == FinvizAuthState.HEALTHY

        try:
            with self._lock:
                now = time.monotonic()
                if now - self._recovery_window_start > RECOVERY_COOLDOWN_S:
                    self._recovery_window_start = now
                    self._recovery_attempts = 0
                if self._recovery_attempts >= MAX_RECOVERY_ATTEMPTS_PER_WINDOW:
                    self._state = FinvizAuthState.AUTH_OPERATOR_ACTION_REQUIRED
                    return False
                self._recovery_attempts += 1
                self._state = FinvizAuthState.REFRESHING

                current_token = self._token

            candidate_token, candidate_source = _configured_token_with_source()
            if (
                candidate_token
                and candidate_token != current_token
                and candidate_source != FinvizCredentialSource.ENVIRONMENT
                and self.validate_token(candidate_token)
            ):
                with self._lock:
                    self._token = candidate_token
                    self._source = candidate_source
                    self._state = FinvizAuthState.HEALTHY
                    self._last_auth_error = None
                    self._metadata = record_credential_activation(
                        source=candidate_source.value,
                        rotated=True,
                    )
                return True

            username, password = read_login_credentials()
            if not username or not password:
                username, password = read_login_credentials_from_env()
            if not username or not password:
                with self._lock:
                    self._state = FinvizAuthState.AUTH_OPERATOR_ACTION_REQUIRED
                    self._last_auth_error = "LOGIN_CREDENTIALS_MISSING"
                return False

            result = recover_token_via_login(username=username, password=password)
            if result.status == LoginRecoveryStatus.REFRESHED and result.token:
                if not self.validate_token(result.token):
                    with self._lock:
                        self._state = FinvizAuthState.AUTH_INVALID
                    return False
                if not write_secure_token(result.token):
                    with self._lock:
                        self._state = FinvizAuthState.ERROR
                    return False
                with self._lock:
                    rotated = self._token != result.token
                    self._token = result.token
                    self._source = FinvizCredentialSource.PRIVATE_FILE
                    self._state = FinvizAuthState.HEALTHY
                    self._metadata = record_credential_activation(
                        source=self._source.value,
                        rotated=rotated,
                    )
                return True

            with self._lock:
                if result.status == LoginRecoveryStatus.MANUAL_AUTH_REQUIRED:
                    self._state = FinvizAuthState.AUTH_OPERATOR_ACTION_REQUIRED
                    self._last_auth_error = "MFA_OR_CAPTCHA"
                else:
                    self._state = FinvizAuthState.AUTH_INVALID
                    self._last_auth_error = result.status.value
            return False
        finally:
            self._recovery_lock.release()

    def mark_rate_limited(self) -> None:
        with self._lock:
            self._state = FinvizAuthState.RATE_LIMITED

    def mark_provider_unavailable(self) -> None:
        with self._lock:
            self._state = FinvizAuthState.PROVIDER_UNAVAILABLE

    def mark_auth_failure(self, kind: FinvizFailureKind) -> None:
        with self._lock:
            self._state = self._state_from_kind(kind)
            self._last_auth_error = kind.value


_MANAGER: FinvizCredentialManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_finviz_credential_manager() -> FinvizCredentialManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = FinvizCredentialManager()
            _MANAGER.load()
        return _MANAGER


def finviz_api_key() -> str | None:
    return get_finviz_credential_manager().get_token()


def reset_finviz_credential_manager() -> None:
    global _MANAGER
    with _MANAGER_LOCK:
        _MANAGER = None
