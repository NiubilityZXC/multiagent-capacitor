"""Auditable, one-shot stdlib HTTPS transport for the Ark Plan data plane.

This module is deliberately narrower than a general HTTP client.  It owns no
environment lookup, logging, redirect handling, retry policy, proxy support, or
connection pool.  A composition root supplies a one-use credential lease.  A
transport instance consumes at most one ``HTTPSConnection.request`` call and
returns a closed, secret-free receipt for both success and failure.

The receipt proves the local call path taken by this concrete implementation;
it is not a server-side assertion that a request was received or executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import http.client
import re
import socket
import ssl
import threading
import time
from typing import Protocol, TypeAlias

from .ark_provider import ArkTransportRequest, ArkTransportResponse
from .canonical import canonical_bytes, canonical_sha256


ARK_PLAN_HOST = "ark.cn-beijing.volces.com"
ARK_PLAN_PORT = 443
ARK_PLAN_BASE_PATH = "/api/plan/v3"
ARK_RESPONSES_PATH = "/responses"
ARK_PLAN_RESPONSES_TARGET = ARK_PLAN_BASE_PATH + ARK_RESPONSES_PATH

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+/-]{0,126}$")
_MAX_CREDENTIAL_BYTES = 4096


class ArkCredentialLease(Protocol):
    """One-use in-memory bearer-token source owned by the composition root."""

    def take(self) -> bytearray:
        """Consume and return a mutable bearer token without the ``Bearer`` prefix."""


class ArkOneShotTransportOutcome(str, Enum):
    """Closed category for one transport invocation."""

    RESPONSE_COMPLETE = "RESPONSE_COMPLETE"
    PRE_REQUEST_FAILURE = "PRE_REQUEST_FAILURE"
    REQUEST_FAILURE = "REQUEST_FAILURE"
    RESPONSE_FAILURE = "RESPONSE_FAILURE"


class ArkOneShotWireState(str, Enum):
    """Furthest locally observed stdlib HTTP state."""

    NOT_CALLED = "NOT_CALLED"
    REQUEST_CALL_RAISED = "REQUEST_CALL_RAISED"
    REQUEST_CALL_RETURNED = "REQUEST_CALL_RETURNED"
    RESPONSE_HEADERS = "RESPONSE_HEADERS"
    RESPONSE_COMPLETE = "RESPONSE_COMPLETE"


class ArkOneShotFailureCode(str, Enum):
    """Closed failure taxonomy; no member contains provider or exception text."""

    ALREADY_CONSUMED = "ALREADY_CONSUMED"
    INVALID_REQUEST = "INVALID_REQUEST"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    DEADLINE_EXPIRED = "DEADLINE_EXPIRED"
    TLS_ERROR = "TLS_ERROR"
    DNS_CONNECT_ERROR = "DNS_CONNECT_ERROR"
    TIMEOUT = "TIMEOUT"
    REQUEST_IO_ERROR = "REQUEST_IO_ERROR"
    RESPONSE_PROTOCOL_ERROR = "RESPONSE_PROTOCOL_ERROR"
    RESPONSE_INCOMPLETE = "RESPONSE_INCOMPLETE"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class ArkOneShotHTTPSProfile:
    """Immutable public configuration for the exact Ark Plan HTTPS lane."""

    max_response_bytes: int = 2_000_000
    host: str = field(default=ARK_PLAN_HOST, init=False)
    port: int = field(default=ARK_PLAN_PORT, init=False)
    base_path: str = field(default=ARK_PLAN_BASE_PATH, init=False)
    endpoint_path: str = field(default=ARK_RESPONSES_PATH, init=False)
    tls_minimum: str = field(default="TLSv1.2", init=False)
    certificate_verification: str = field(default="CERT_REQUIRED", init=False)
    hostname_verification: bool = field(default=True, init=False)
    alpn_protocol: str = field(default="http/1.1", init=False)
    proxy_mode: str = field(default="forbidden", init=False)
    connection_reuse: bool = field(default=False, init=False)
    retries: int = field(default=0, init=False)
    redirects_followed: int = field(default=0, init=False)
    implementation: str = field(
        default="stdlib_http_client_https_oneshot_v1", init=False
    )
    schema_version: str = field(default="ArkOneShotHTTPSProfile.v1", init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_response_bytes, bool)
            or not isinstance(self.max_response_bytes, int)
            or not 1 <= self.max_response_bytes <= 16_000_000
        ):
            raise ValueError("invalid one-shot response byte ceiling")

    @property
    def request_target(self) -> str:
        return self.base_path + self.endpoint_path

    @property
    def profile_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ArkOneShotTransportReceipt:
    """Typed, secret-free evidence for one local transport invocation."""

    profile_hash: str
    request_target: str
    request_body_sha256: str
    request_body_bytes: int
    nonsecret_headers_sha256: str
    started_unix_ms: int
    completed_unix_ms: int
    auth_header_attached: bool
    connection_objects: int
    request_calls: int
    getresponse_calls: int
    body_read_calls: int
    retries: int
    redirects_followed: int
    outcome: ArkOneShotTransportOutcome
    wire_state: ArkOneShotWireState
    failure_code: ArkOneShotFailureCode | None
    http_status: int | None
    response_complete: bool
    observed_response_sha256: str | None
    observed_response_bytes: int | None
    response_media_type: str | None
    schema_version: str = field(default="ArkOneShotTransportReceipt.v1", init=False)

    def __post_init__(self) -> None:
        for name in (
            "profile_hash",
            "request_body_sha256",
            "nonsecret_headers_sha256",
        ):
            if _SHA256_RE.fullmatch(getattr(self, name)) is None:
                raise ValueError(f"invalid {name}")
        if self.request_target != ARK_PLAN_RESPONSES_TARGET:
            raise ValueError("invalid one-shot request target")
        for name in (
            "request_body_bytes",
            "started_unix_ms",
            "completed_unix_ms",
            "connection_objects",
            "request_calls",
            "getresponse_calls",
            "body_read_calls",
            "retries",
            "redirects_followed",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"invalid {name}")
        if self.completed_unix_ms < self.started_unix_ms:
            raise ValueError("transport completion precedes start")
        if any(
            value > 1
            for value in (
                self.connection_objects,
                self.request_calls,
                self.getresponse_calls,
                self.body_read_calls,
            )
        ):
            raise ValueError("one-shot receipt contains repeated calls")
        if self.retries != 0 or self.redirects_followed != 0:
            raise ValueError("one-shot receipt cannot contain retries or redirects")
        if self.getresponse_calls > self.request_calls:
            raise ValueError("getresponse call lacks request call")
        if self.body_read_calls > self.getresponse_calls:
            raise ValueError("response read lacks getresponse call")
        if self.request_calls and (
            not self.auth_header_attached or self.connection_objects != 1
        ):
            raise ValueError("request call lacks authorization or connection evidence")
        if not isinstance(self.outcome, ArkOneShotTransportOutcome) or not isinstance(
            self.wire_state, ArkOneShotWireState
        ):
            raise ValueError("invalid one-shot outcome")
        if self.failure_code is not None and not isinstance(
            self.failure_code, ArkOneShotFailureCode
        ):
            raise ValueError("invalid one-shot failure code")
        if self.http_status is not None and (
            isinstance(self.http_status, bool)
            or not isinstance(self.http_status, int)
            or not 100 <= self.http_status <= 599
        ):
            raise ValueError("invalid HTTP status evidence")
        if (self.observed_response_sha256 is None) != (
            self.observed_response_bytes is None
        ):
            raise ValueError("observed response hash and size must be paired")
        if self.observed_response_sha256 is not None:
            if _SHA256_RE.fullmatch(self.observed_response_sha256) is None:
                raise ValueError("invalid observed response hash")
            if (
                isinstance(self.observed_response_bytes, bool)
                or not isinstance(self.observed_response_bytes, int)
                or self.observed_response_bytes < 0
            ):
                raise ValueError("invalid observed response size")
        if self.response_media_type is not None and (
            not isinstance(self.response_media_type, str)
            or _MEDIA_TYPE_RE.fullmatch(self.response_media_type) is None
        ):
            raise ValueError("invalid response media type evidence")

        if self.outcome is ArkOneShotTransportOutcome.RESPONSE_COMPLETE:
            if (
                self.failure_code is not None
                or self.wire_state is not ArkOneShotWireState.RESPONSE_COMPLETE
                or not self.response_complete
                or self.connection_objects != 1
                or self.request_calls != 1
                or self.getresponse_calls != 1
                or self.body_read_calls != 1
                or self.http_status is None
                or self.observed_response_sha256 is None
            ):
                raise ValueError("complete response receipt is inconsistent")
        else:
            if self.failure_code is None or self.response_complete:
                raise ValueError("failed transport receipt is inconsistent")
            if self.outcome is ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE and (
                self.wire_state is not ArkOneShotWireState.NOT_CALLED
                or self.request_calls != 0
                or self.getresponse_calls != 0
                or self.body_read_calls != 0
            ):
                raise ValueError("pre-request failure contains request evidence")
            if self.outcome is ArkOneShotTransportOutcome.REQUEST_FAILURE and (
                self.wire_state is not ArkOneShotWireState.REQUEST_CALL_RAISED
                or self.request_calls != 1
                or self.getresponse_calls != 0
                or self.body_read_calls != 0
            ):
                raise ValueError("request failure receipt is inconsistent")
            if self.outcome is ArkOneShotTransportOutcome.RESPONSE_FAILURE and (
                self.request_calls != 1
                or self.wire_state
                not in {
                    ArkOneShotWireState.REQUEST_CALL_RETURNED,
                    ArkOneShotWireState.RESPONSE_HEADERS,
                }
            ):
                raise ValueError("response failure receipt is inconsistent")

    @property
    def receipt_hash(self) -> str:
        return canonical_sha256(self)

    @classmethod
    def from_mapping(cls, payload: object) -> "ArkOneShotTransportReceipt":
        """Rebuild and byte-check one persisted secret-free receipt."""

        expected = {
            "schema_version",
            "profile_hash",
            "request_target",
            "request_body_sha256",
            "request_body_bytes",
            "nonsecret_headers_sha256",
            "started_unix_ms",
            "completed_unix_ms",
            "auth_header_attached",
            "connection_objects",
            "request_calls",
            "getresponse_calls",
            "body_read_calls",
            "retries",
            "redirects_followed",
            "outcome",
            "wire_state",
            "failure_code",
            "http_status",
            "response_complete",
            "observed_response_sha256",
            "observed_response_bytes",
            "response_media_type",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError("persisted one-shot receipt has the wrong fields")
        if payload["schema_version"] != "ArkOneShotTransportReceipt.v1":
            raise ValueError("persisted one-shot receipt has the wrong version")
        try:
            value = cls(
                profile_hash=payload["profile_hash"],
                request_target=payload["request_target"],
                request_body_sha256=payload["request_body_sha256"],
                request_body_bytes=payload["request_body_bytes"],
                nonsecret_headers_sha256=payload["nonsecret_headers_sha256"],
                started_unix_ms=payload["started_unix_ms"],
                completed_unix_ms=payload["completed_unix_ms"],
                auth_header_attached=payload["auth_header_attached"],
                connection_objects=payload["connection_objects"],
                request_calls=payload["request_calls"],
                getresponse_calls=payload["getresponse_calls"],
                body_read_calls=payload["body_read_calls"],
                retries=payload["retries"],
                redirects_followed=payload["redirects_followed"],
                outcome=ArkOneShotTransportOutcome(payload["outcome"]),
                wire_state=ArkOneShotWireState(payload["wire_state"]),
                failure_code=(
                    ArkOneShotFailureCode(payload["failure_code"])
                    if payload["failure_code"] is not None
                    else None
                ),
                http_status=payload["http_status"],
                response_complete=payload["response_complete"],
                observed_response_sha256=payload["observed_response_sha256"],
                observed_response_bytes=payload["observed_response_bytes"],
                response_media_type=payload["response_media_type"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("persisted one-shot receipt is invalid") from exc
        if canonical_bytes(payload) != canonical_bytes(value):
            raise ValueError("persisted one-shot receipt is not canonical")
        return value


@dataclass(frozen=True, slots=True)
class ArkOneShotTransportSuccess:
    """A complete HTTP response plus its typed one-shot receipt."""

    response: ArkTransportResponse = field(repr=False)
    receipt: ArkOneShotTransportReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.response, ArkTransportResponse) or not isinstance(
            self.receipt, ArkOneShotTransportReceipt
        ):
            raise TypeError("invalid one-shot transport success")
        media_type = _normalise_media_type(self.response.content_type)
        if (
            self.receipt.outcome is not ArkOneShotTransportOutcome.RESPONSE_COMPLETE
            or self.receipt.completed_unix_ms != self.response.completed_unix_ms
            or self.receipt.http_status != self.response.status_code
            or self.receipt.observed_response_sha256
            != hashlib.sha256(self.response.body).hexdigest()
            or self.receipt.observed_response_bytes != len(self.response.body)
            or self.receipt.response_media_type != media_type
        ):
            raise ValueError("response and one-shot receipt differ")


@dataclass(frozen=True, slots=True)
class ArkOneShotTransportFailure:
    """A closed failure with no raw exception, response, or credential text."""

    code: ArkOneShotFailureCode
    receipt: ArkOneShotTransportReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.code, ArkOneShotFailureCode) or not isinstance(
            self.receipt, ArkOneShotTransportReceipt
        ):
            raise TypeError("invalid one-shot transport failure")
        if (
            self.receipt.failure_code is not self.code
            or self.receipt.outcome is ArkOneShotTransportOutcome.RESPONSE_COMPLETE
        ):
            raise ValueError("failure and one-shot receipt differ")


ArkOneShotTransportResult: TypeAlias = (
    ArkOneShotTransportSuccess | ArkOneShotTransportFailure
)


def _now_unix_ms() -> int:
    return time.time_ns() // 1_000_000


def _normalise_media_type(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    media_type = value.split(";", 1)[0].strip().lower()
    if not media_type or _MEDIA_TYPE_RE.fullmatch(media_type) is None:
        return None
    return media_type


def _wipe(value: bytearray | None) -> None:
    if value is not None:
        for index in range(len(value)):
            value[index] = 0


def _strict_tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_alpn_protocols(["http/1.1"])
    return context


class StdlibHTTPSOneShotTransport:
    """Single-use Ark Plan transport with one static stdlib request call site."""

    def __init__(
        self,
        *,
        profile: ArkOneShotHTTPSProfile,
        credential_lease: ArkCredentialLease,
    ) -> None:
        if not isinstance(profile, ArkOneShotHTTPSProfile):
            raise TypeError("profile must be ArkOneShotHTTPSProfile")
        self._profile = profile
        self._credential_lease = credential_lease
        self._lock = threading.Lock()
        self._used = False

    @property
    def profile(self) -> ArkOneShotHTTPSProfile:
        return self._profile

    def _receipt(
        self,
        *,
        request_body_sha256: str,
        request_body_bytes: int,
        nonsecret_headers_sha256: str,
        started_unix_ms: int,
        authorization_injected: bool,
        connection_objects: int,
        request_calls: int,
        getresponse_calls: int,
        body_read_calls: int,
        outcome: ArkOneShotTransportOutcome,
        wire_state: ArkOneShotWireState,
        failure_code: ArkOneShotFailureCode | None,
        http_status: int | None = None,
        response_complete: bool = False,
        observed_response: bytes | None = None,
        response_media_type: str | None = None,
    ) -> ArkOneShotTransportReceipt:
        completed = max(started_unix_ms, _now_unix_ms())
        return ArkOneShotTransportReceipt(
            profile_hash=self._profile.profile_hash,
            request_target=self._profile.request_target,
            request_body_sha256=request_body_sha256,
            request_body_bytes=request_body_bytes,
            nonsecret_headers_sha256=nonsecret_headers_sha256,
            started_unix_ms=started_unix_ms,
            completed_unix_ms=completed,
            auth_header_attached=authorization_injected,
            connection_objects=connection_objects,
            request_calls=request_calls,
            getresponse_calls=getresponse_calls,
            body_read_calls=body_read_calls,
            retries=0,
            redirects_followed=0,
            outcome=outcome,
            wire_state=wire_state,
            failure_code=failure_code,
            http_status=http_status,
            response_complete=response_complete,
            observed_response_sha256=hashlib.sha256(observed_response).hexdigest()
            if observed_response is not None
            else None,
            observed_response_bytes=len(observed_response)
            if observed_response is not None
            else None,
            response_media_type=response_media_type,
        )

    def _failure(
        self,
        *,
        code: ArkOneShotFailureCode,
        outcome: ArkOneShotTransportOutcome,
        wire_state: ArkOneShotWireState,
        request_body_sha256: str,
        request_body_bytes: int,
        nonsecret_headers_sha256: str,
        started_unix_ms: int,
        authorization_injected: bool,
        connection_objects: int,
        request_calls: int,
        getresponse_calls: int,
        body_read_calls: int,
        http_status: int | None = None,
        observed_response: bytes | None = None,
        response_media_type: str | None = None,
    ) -> ArkOneShotTransportFailure:
        return ArkOneShotTransportFailure(
            code=code,
            receipt=self._receipt(
                request_body_sha256=request_body_sha256,
                request_body_bytes=request_body_bytes,
                nonsecret_headers_sha256=nonsecret_headers_sha256,
                started_unix_ms=started_unix_ms,
                authorization_injected=authorization_injected,
                connection_objects=connection_objects,
                request_calls=request_calls,
                getresponse_calls=getresponse_calls,
                body_read_calls=body_read_calls,
                outcome=outcome,
                wire_state=wire_state,
                failure_code=code,
                http_status=http_status,
                observed_response=observed_response,
                response_media_type=response_media_type,
            ),
        )

    def send(self, request: ArkTransportRequest) -> ArkOneShotTransportResult:
        """Consume this transport and perform at most one HTTPS request call."""

        started = _now_unix_ms()
        with self._lock:
            already_used = self._used
            self._used = True

        valid_request = isinstance(request, ArkTransportRequest)
        request_body = request.body if valid_request else b""
        request_body_hash = hashlib.sha256(request_body).hexdigest()
        request_body_bytes = len(request_body)
        nonsecret_headers: dict[str, str] = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "Content-Length": str(request_body_bytes),
            "Content-Type": "application/json",
            "Host": self._profile.host,
        }
        nonsecret_headers_hash = canonical_sha256(
            {"headers": tuple(sorted(nonsecret_headers.items()))}
        )
        common = {
            "request_body_sha256": request_body_hash,
            "request_body_bytes": request_body_bytes,
            "nonsecret_headers_sha256": nonsecret_headers_hash,
            "started_unix_ms": started,
        }

        if already_used:
            return self._failure(
                code=ArkOneShotFailureCode.ALREADY_CONSUMED,
                outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                wire_state=ArkOneShotWireState.NOT_CALLED,
                authorization_injected=False,
                connection_objects=0,
                request_calls=0,
                getresponse_calls=0,
                body_read_calls=0,
                **common,
            )
        if not valid_request or request.path != self._profile.endpoint_path:
            return self._failure(
                code=ArkOneShotFailureCode.INVALID_REQUEST,
                outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                wire_state=ArkOneShotWireState.NOT_CALLED,
                authorization_injected=False,
                connection_objects=0,
                request_calls=0,
                getresponse_calls=0,
                body_read_calls=0,
                **common,
            )
        remaining_ms = min(request.timeout_ms, request.deadline_unix_ms - started)
        if remaining_ms <= 0:
            return self._failure(
                code=ArkOneShotFailureCode.DEADLINE_EXPIRED,
                outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                wire_state=ArkOneShotWireState.NOT_CALLED,
                authorization_injected=False,
                connection_objects=0,
                request_calls=0,
                getresponse_calls=0,
                body_read_calls=0,
                **common,
            )

        credential: bytearray | None = None
        authorization: bytes | None = None
        headers: dict[str, str | bytes] = dict(nonsecret_headers)
        try:
            try:
                credential = self._credential_lease.take()
            except Exception:
                return self._failure(
                    code=ArkOneShotFailureCode.CREDENTIAL_UNAVAILABLE,
                    outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                    wire_state=ArkOneShotWireState.NOT_CALLED,
                    authorization_injected=False,
                    connection_objects=0,
                    request_calls=0,
                    getresponse_calls=0,
                    body_read_calls=0,
                    **common,
                )
            if (
                not isinstance(credential, bytearray)
                or not credential
                or len(credential) > _MAX_CREDENTIAL_BYTES
                or any(byte < 0x21 or byte > 0x7E for byte in credential)
            ):
                return self._failure(
                    code=ArkOneShotFailureCode.INVALID_CREDENTIAL,
                    outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                    wire_state=ArkOneShotWireState.NOT_CALLED,
                    authorization_injected=False,
                    connection_objects=0,
                    request_calls=0,
                    getresponse_calls=0,
                    body_read_calls=0,
                    **common,
                )
            authorization = b"Bearer " + bytes(credential)
            headers["Authorization"] = authorization

            try:
                context = _strict_tls_context()
                connection = http.client.HTTPSConnection(
                    self._profile.host,
                    self._profile.port,
                    timeout=remaining_ms / 1000.0,
                    context=context,
                )
            except ssl.SSLError:
                return self._failure(
                    code=ArkOneShotFailureCode.TLS_ERROR,
                    outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                    wire_state=ArkOneShotWireState.NOT_CALLED,
                    authorization_injected=True,
                    connection_objects=0,
                    request_calls=0,
                    getresponse_calls=0,
                    body_read_calls=0,
                    **common,
                )
            except Exception:
                return self._failure(
                    code=ArkOneShotFailureCode.INTERNAL_ERROR,
                    outcome=ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE,
                    wire_state=ArkOneShotWireState.NOT_CALLED,
                    authorization_injected=True,
                    connection_objects=0,
                    request_calls=0,
                    getresponse_calls=0,
                    body_read_calls=0,
                    **common,
                )

            response = None
            try:
                try:
                    connection.request(
                        "POST",
                        self._profile.request_target,
                        body=request_body,
                        headers=headers,
                        encode_chunked=False,
                    )
                except TimeoutError:
                    return self._failure(
                        code=ArkOneShotFailureCode.TIMEOUT,
                        outcome=ArkOneShotTransportOutcome.REQUEST_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RAISED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=0,
                        body_read_calls=0,
                        **common,
                    )
                except ssl.SSLError:
                    return self._failure(
                        code=ArkOneShotFailureCode.TLS_ERROR,
                        outcome=ArkOneShotTransportOutcome.REQUEST_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RAISED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=0,
                        body_read_calls=0,
                        **common,
                    )
                except socket.gaierror:
                    return self._failure(
                        code=ArkOneShotFailureCode.DNS_CONNECT_ERROR,
                        outcome=ArkOneShotTransportOutcome.REQUEST_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RAISED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=0,
                        body_read_calls=0,
                        **common,
                    )
                except (http.client.HTTPException, OSError):
                    return self._failure(
                        code=ArkOneShotFailureCode.REQUEST_IO_ERROR,
                        outcome=ArkOneShotTransportOutcome.REQUEST_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RAISED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=0,
                        body_read_calls=0,
                        **common,
                    )
                except Exception:
                    return self._failure(
                        code=ArkOneShotFailureCode.INTERNAL_ERROR,
                        outcome=ArkOneShotTransportOutcome.REQUEST_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RAISED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=0,
                        body_read_calls=0,
                        **common,
                    )
                finally:
                    headers.pop("Authorization", None)
                    authorization = None
                    _wipe(credential)

                try:
                    response = connection.getresponse()
                except TimeoutError:
                    return self._failure(
                        code=ArkOneShotFailureCode.TIMEOUT,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RETURNED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=0,
                        **common,
                    )
                except ssl.SSLError:
                    return self._failure(
                        code=ArkOneShotFailureCode.TLS_ERROR,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RETURNED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=0,
                        **common,
                    )
                except Exception:
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.REQUEST_CALL_RETURNED,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=0,
                        **common,
                    )

                try:
                    status = response.status
                    content_type = response.getheader("Content-Type", "")
                    content_encoding = response.getheader("Content-Encoding", "")
                except Exception:
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=0,
                        **common,
                    )
                media_type = _normalise_media_type(content_type)
                if (
                    isinstance(status, bool)
                    or not isinstance(status, int)
                    or not 100 <= status <= 599
                    or (content_type and media_type is None)
                    or (
                        isinstance(content_encoding, str)
                        and content_encoding.strip().lower() not in {"", "identity"}
                    )
                    or not isinstance(content_encoding, str)
                ):
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=0,
                        http_status=status
                        if isinstance(status, int)
                        and not isinstance(status, bool)
                        and 100 <= status <= 599
                        else None,
                        response_media_type=media_type,
                        **common,
                    )

                try:
                    body = response.read(self._profile.max_response_bytes + 1)
                except http.client.IncompleteRead as error:
                    partial = error.partial
                    if not isinstance(partial, bytes):
                        partial = b""
                    partial = partial[: self._profile.max_response_bytes + 1]
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_INCOMPLETE,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=1,
                        http_status=status,
                        observed_response=partial,
                        response_media_type=media_type,
                        **common,
                    )
                except TimeoutError:
                    return self._failure(
                        code=ArkOneShotFailureCode.TIMEOUT,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=1,
                        http_status=status,
                        response_media_type=media_type,
                        **common,
                    )
                except Exception:
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=1,
                        http_status=status,
                        response_media_type=media_type,
                        **common,
                    )
                if not isinstance(body, bytes):
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=1,
                        http_status=status,
                        response_media_type=media_type,
                        **common,
                    )
                if len(body) > self._profile.max_response_bytes:
                    return self._failure(
                        code=ArkOneShotFailureCode.RESPONSE_TOO_LARGE,
                        outcome=ArkOneShotTransportOutcome.RESPONSE_FAILURE,
                        wire_state=ArkOneShotWireState.RESPONSE_HEADERS,
                        authorization_injected=True,
                        connection_objects=1,
                        request_calls=1,
                        getresponse_calls=1,
                        body_read_calls=1,
                        http_status=status,
                        observed_response=body,
                        response_media_type=media_type,
                        **common,
                    )

                receipt = self._receipt(
                    request_body_sha256=request_body_hash,
                    request_body_bytes=request_body_bytes,
                    nonsecret_headers_sha256=nonsecret_headers_hash,
                    started_unix_ms=started,
                    authorization_injected=True,
                    connection_objects=1,
                    request_calls=1,
                    getresponse_calls=1,
                    body_read_calls=1,
                    outcome=ArkOneShotTransportOutcome.RESPONSE_COMPLETE,
                    wire_state=ArkOneShotWireState.RESPONSE_COMPLETE,
                    failure_code=None,
                    http_status=status,
                    response_complete=True,
                    observed_response=body,
                    response_media_type=media_type,
                )
                transport_response = ArkTransportResponse(
                    status_code=status,
                    body=body,
                    completed_unix_ms=receipt.completed_unix_ms,
                    content_type=media_type or "",
                )
                return ArkOneShotTransportSuccess(transport_response, receipt)
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass
                try:
                    connection.close()
                except Exception:
                    pass
        finally:
            headers.pop("Authorization", None)
            authorization = None
            _wipe(credential)


__all__ = [
    "ARK_PLAN_BASE_PATH",
    "ARK_PLAN_HOST",
    "ARK_PLAN_PORT",
    "ARK_PLAN_RESPONSES_TARGET",
    "ARK_RESPONSES_PATH",
    "ArkCredentialLease",
    "ArkOneShotFailureCode",
    "ArkOneShotHTTPSProfile",
    "ArkOneShotTransportFailure",
    "ArkOneShotTransportOutcome",
    "ArkOneShotTransportReceipt",
    "ArkOneShotTransportResult",
    "ArkOneShotTransportSuccess",
    "ArkOneShotWireState",
    "StdlibHTTPSOneShotTransport",
]
