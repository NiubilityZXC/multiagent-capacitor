from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import http.client
from pathlib import Path
import socket
import ssl
import threading
from typing import Any

import pytest

from experiments.vfps_agent.ark_provider import ArkTransportRequest
from experiments.vfps_agent import ark_https_transport as transport_module
from experiments.vfps_agent.ark_https_transport import (
    ARK_PLAN_BASE_PATH,
    ARK_PLAN_HOST,
    ARK_PLAN_PORT,
    ARK_PLAN_RESPONSES_TARGET,
    ARK_RESPONSES_PATH,
    ArkOneShotFailureCode,
    ArkOneShotHTTPSProfile,
    ArkOneShotTransportFailure,
    ArkOneShotTransportOutcome,
    ArkOneShotTransportSuccess,
    ArkOneShotWireState,
    StdlibHTTPSOneShotTransport,
)


class FakeCredentialLease:
    def __init__(
        self,
        token: bytearray | None = None,
        error: Exception | None = None,
    ) -> None:
        self.token = token if token is not None else bytearray(b"offline-test-token")
        self.error = error
        self.calls = 0

    def take(self) -> bytearray:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.token


class FakeHTTPResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b'{"ok":true}',
        headers: dict[str, str] | None = None,
        read_error: Exception | None = None,
        header_error: Exception | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Encoding": "identity",
            **(headers or {}),
        }
        self.read_error = read_error
        self.header_error = header_error
        self.header_reads: list[str] = []
        self.read_calls = 0
        self.read_amounts: list[int] = []
        self.closed = False

    def getheader(self, name: str, default: str = "") -> str:
        self.header_reads.append(name)
        if self.header_error is not None:
            raise self.header_error
        return self.headers.get(name, default)

    def read(self, amount: int) -> bytes:
        self.read_calls += 1
        self.read_amounts.append(amount)
        if self.read_error is not None:
            raise self.read_error
        return self.body[:amount]

    def close(self) -> None:
        self.closed = True


class FakeHTTPSConnection:
    def __init__(
        self,
        factory: "FakeHTTPSConnectionFactory",
        host: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        self.factory = factory
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.request_calls = 0
        self.getresponse_calls = 0
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method: str,
        target: str,
        *,
        body: bytes,
        headers: dict[str, str | bytes],
        encode_chunked: bool,
    ) -> None:
        self.request_calls += 1
        self.requests.append(
            {
                "method": method,
                "target": target,
                "body": bytes(body),
                "headers": dict(headers),
                "encode_chunked": encode_chunked,
            }
        )
        if self.factory.request_entered is not None:
            self.factory.request_entered.set()
        if self.factory.request_release is not None:
            assert self.factory.request_release.wait(timeout=5)
        if self.factory.request_error is not None:
            raise self.factory.request_error

    def getresponse(self) -> FakeHTTPResponse:
        self.getresponse_calls += 1
        if self.factory.getresponse_error is not None:
            raise self.factory.getresponse_error
        return self.factory.response

    def close(self) -> None:
        self.closed = True


class FakeHTTPSConnectionFactory:
    def __init__(
        self,
        response: FakeHTTPResponse | None = None,
        *,
        request_error: Exception | None = None,
        getresponse_error: Exception | None = None,
        request_entered: threading.Event | None = None,
        request_release: threading.Event | None = None,
    ) -> None:
        self.response = response if response is not None else FakeHTTPResponse()
        self.request_error = request_error
        self.getresponse_error = getresponse_error
        self.request_entered = request_entered
        self.request_release = request_release
        self.instances: list[FakeHTTPSConnection] = []

    def __call__(
        self,
        host: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> FakeHTTPSConnection:
        connection = FakeHTTPSConnection(
            self,
            host,
            port,
            timeout=timeout,
            context=context,
        )
        self.instances.append(connection)
        return connection


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transport_module, "_now_unix_ms", lambda: 1_000)


def request_fixture(*, deadline_unix_ms: int = 2_000) -> ArkTransportRequest:
    return ArkTransportRequest(
        method="POST",
        path="/responses",
        body=b'{"fixture":"offline"}',
        deadline_unix_ms=deadline_unix_ms,
        timeout_ms=1_000,
    )


def transport_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: FakeHTTPResponse | None = None,
    request_error: Exception | None = None,
    getresponse_error: Exception | None = None,
    lease: FakeCredentialLease | None = None,
    profile: ArkOneShotHTTPSProfile | None = None,
    request_entered: threading.Event | None = None,
    request_release: threading.Event | None = None,
) -> tuple[
    StdlibHTTPSOneShotTransport,
    FakeHTTPSConnectionFactory,
    FakeCredentialLease,
]:
    factory = FakeHTTPSConnectionFactory(
        response,
        request_error=request_error,
        getresponse_error=getresponse_error,
        request_entered=request_entered,
        request_release=request_release,
    )
    monkeypatch.setattr(transport_module.http.client, "HTTPSConnection", factory)
    selected_lease = lease if lease is not None else FakeCredentialLease()
    transport = StdlibHTTPSOneShotTransport(
        profile=profile if profile is not None else ArkOneShotHTTPSProfile(),
        credential_lease=selected_lease,
    )
    return transport, factory, selected_lease


def test_profile_is_immutable_and_exactly_fixes_plan_origin() -> None:
    profile = ArkOneShotHTTPSProfile(max_response_bytes=1234)
    assert profile.host == ARK_PLAN_HOST == "ark.cn-beijing.volces.com"
    assert profile.port == ARK_PLAN_PORT == 443
    assert profile.base_path == ARK_PLAN_BASE_PATH == "/api/plan/v3"
    assert profile.endpoint_path == ARK_RESPONSES_PATH == "/responses"
    assert profile.request_target == ARK_PLAN_RESPONSES_TARGET
    assert profile.retries == profile.redirects_followed == 0
    assert profile.proxy_mode == "forbidden"
    assert profile.connection_reuse is False
    assert len(profile.profile_hash) == 64
    with pytest.raises(FrozenInstanceError):
        profile.max_response_bytes = 5  # type: ignore[misc]
    with pytest.raises(ValueError):
        ArkOneShotHTTPSProfile(max_response_bytes=0)


def test_success_uses_one_https_request_and_emits_bound_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeHTTPResponse(body=b'{"answer":0.5}')
    transport, factory, lease = transport_fixture(monkeypatch, response=response)
    request = request_fixture()

    result = transport.send(request)

    assert isinstance(result, ArkOneShotTransportSuccess)
    assert len(factory.instances) == 1
    connection = factory.instances[0]
    assert connection.host == ARK_PLAN_HOST
    assert connection.port == 443
    assert connection.timeout == 1.0
    assert connection.context.check_hostname is True
    assert connection.context.verify_mode == ssl.CERT_REQUIRED
    assert connection.context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert connection.request_calls == connection.getresponse_calls == 1
    assert connection.closed and response.closed
    sent = connection.requests[0]
    assert sent["method"] == "POST"
    assert sent["target"] == "/api/plan/v3/responses"
    assert sent["body"] == request.body
    assert sent["encode_chunked"] is False
    assert sent["headers"]["Authorization"] == b"Bearer offline-test-token"
    assert sent["headers"]["Connection"] == "close"
    assert sent["headers"]["Accept-Encoding"] == "identity"
    assert sent["headers"]["Host"] == ARK_PLAN_HOST
    assert sent["headers"]["Content-Length"] == str(len(request.body))
    assert response.read_calls == 1
    assert response.read_amounts == [transport.profile.max_response_bytes + 1]
    assert lease.calls == 1
    assert lease.token == bytearray(len(lease.token))

    receipt = result.receipt
    assert receipt.outcome is ArkOneShotTransportOutcome.RESPONSE_COMPLETE
    assert receipt.wire_state is ArkOneShotWireState.RESPONSE_COMPLETE
    assert receipt.connection_objects == 1
    assert receipt.request_calls == receipt.getresponse_calls == receipt.body_read_calls == 1
    assert receipt.retries == receipt.redirects_followed == 0
    assert receipt.http_status == 200
    assert receipt.response_complete
    assert receipt.observed_response_sha256 == hashlib.sha256(response.body).hexdigest()
    assert receipt.observed_response_bytes == len(response.body)
    assert receipt.response_media_type == "application/json"
    assert len(receipt.receipt_hash) == 64
    assert "offline-test-token" not in repr(result)
    with pytest.raises(FrozenInstanceError):
        receipt.request_calls = 2  # type: ignore[misc]
    with pytest.raises(ValueError):
        replace(receipt, request_calls=0)


@pytest.mark.parametrize("status", [301, 307, 401, 403, 429, 500])
def test_http_statuses_are_terminal_responses_without_redirect_or_retry(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    response = FakeHTTPResponse(
        status=status,
        body=b'{"terminal":true}',
        headers={"Location": "https://example.invalid/forbidden"},
    )
    transport, factory, _ = transport_fixture(monkeypatch, response=response)

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportSuccess)
    assert result.response.status_code == status
    assert result.receipt.request_calls == 1
    assert result.receipt.redirects_followed == result.receipt.retries == 0
    assert len(factory.instances) == 1
    assert factory.instances[0].request_calls == 1
    assert "Location" not in response.header_reads


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("CANARY_DO_NOT_PERSIST_timeout"), ArkOneShotFailureCode.TIMEOUT),
        (ssl.SSLError("CANARY_DO_NOT_PERSIST_tls"), ArkOneShotFailureCode.TLS_ERROR),
        (
            socket.gaierror("CANARY_DO_NOT_PERSIST_dns"),
            ArkOneShotFailureCode.DNS_CONNECT_ERROR,
        ),
        (
            ConnectionResetError("CANARY_DO_NOT_PERSIST_reset"),
            ArkOneShotFailureCode.REQUEST_IO_ERROR,
        ),
        (
            RuntimeError("CANARY_DO_NOT_PERSIST_internal"),
            ArkOneShotFailureCode.INTERNAL_ERROR,
        ),
    ],
)
def test_request_exceptions_are_closed_after_one_call_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected: ArkOneShotFailureCode,
) -> None:
    transport, factory, _ = transport_fixture(monkeypatch, request_error=error)

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is expected
    assert result.receipt.outcome is ArkOneShotTransportOutcome.REQUEST_FAILURE
    assert result.receipt.wire_state is ArkOneShotWireState.REQUEST_CALL_RAISED
    assert result.receipt.request_calls == 1
    assert result.receipt.getresponse_calls == result.receipt.body_read_calls == 0
    assert result.receipt.retries == result.receipt.redirects_followed == 0
    assert len(factory.instances) == 1
    assert factory.instances[0].request_calls == 1
    assert factory.instances[0].closed
    assert "CANARY_DO_NOT_PERSIST" not in repr(result)


def test_getresponse_exception_is_closed_without_a_second_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, factory, _ = transport_fixture(
        monkeypatch,
        getresponse_error=RuntimeError("CANARY_DO_NOT_PERSIST_headers"),
    )

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR
    assert result.receipt.outcome is ArkOneShotTransportOutcome.RESPONSE_FAILURE
    assert result.receipt.wire_state is ArkOneShotWireState.REQUEST_CALL_RETURNED
    assert result.receipt.request_calls == result.receipt.getresponse_calls == 1
    assert result.receipt.body_read_calls == 0
    assert factory.instances[0].request_calls == 1
    assert "CANARY_DO_NOT_PERSIST" not in repr(result)


@pytest.mark.parametrize(
    ("read_error", "expected"),
    [
        (
            http.client.IncompleteRead(b"CANARY_DO_NOT_PERSIST_partial", 100),
            ArkOneShotFailureCode.RESPONSE_INCOMPLETE,
        ),
        (TimeoutError("CANARY_DO_NOT_PERSIST_read"), ArkOneShotFailureCode.TIMEOUT),
        (
            RuntimeError("CANARY_DO_NOT_PERSIST_read_internal"),
            ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR,
        ),
    ],
)
def test_read_exceptions_are_terminal_bounded_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    read_error: Exception,
    expected: ArkOneShotFailureCode,
) -> None:
    response = FakeHTTPResponse(read_error=read_error)
    transport, factory, _ = transport_fixture(monkeypatch, response=response)

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is expected
    assert result.receipt.request_calls == 1
    assert result.receipt.getresponse_calls == result.receipt.body_read_calls == 1
    assert result.receipt.wire_state is ArkOneShotWireState.RESPONSE_HEADERS
    assert response.read_amounts == [transport.profile.max_response_bytes + 1]
    assert factory.instances[0].request_calls == 1
    assert "CANARY_DO_NOT_PERSIST" not in repr(result)
    if expected is ArkOneShotFailureCode.RESPONSE_INCOMPLETE:
        partial = b"CANARY_DO_NOT_PERSIST_partial"
        assert result.receipt.observed_response_sha256 == hashlib.sha256(partial).hexdigest()
        assert result.receipt.observed_response_bytes == len(partial)


def test_credential_crlf_and_credential_exception_fail_before_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = bytearray(b"token\r\nAuthorization: injected")
    lease = FakeCredentialLease(token=token)
    transport, factory, _ = transport_fixture(monkeypatch, lease=lease)

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is ArkOneShotFailureCode.INVALID_CREDENTIAL
    assert result.receipt.outcome is ArkOneShotTransportOutcome.PRE_REQUEST_FAILURE
    assert result.receipt.connection_objects == result.receipt.request_calls == 0
    assert factory.instances == []
    assert token == bytearray(len(token))
    assert "Authorization" not in repr(result)

    failing_lease = FakeCredentialLease(
        error=RuntimeError("CANARY_DO_NOT_PERSIST_credential")
    )
    second, second_factory, _ = transport_fixture(monkeypatch, lease=failing_lease)
    second_result = second.send(request_fixture())
    assert isinstance(second_result, ArkOneShotTransportFailure)
    assert second_result.code is ArkOneShotFailureCode.CREDENTIAL_UNAVAILABLE
    assert second_result.receipt.request_calls == 0
    assert second_factory.instances == []
    assert "CANARY_DO_NOT_PERSIST" not in repr(second_result)


def test_expired_deadline_fails_before_credential_or_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, factory, lease = transport_fixture(monkeypatch)

    result = transport.send(request_fixture(deadline_unix_ms=999))

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is ArkOneShotFailureCode.DEADLINE_EXPIRED
    assert result.receipt.wire_state is ArkOneShotWireState.NOT_CALLED
    assert result.receipt.request_calls == 0
    assert lease.calls == 0
    assert factory.instances == []


def test_oversized_response_reads_once_to_ceiling_plus_one_and_returns_no_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = ArkOneShotHTTPSProfile(max_response_bytes=4)
    response = FakeHTTPResponse(body=b"123456789")
    transport, factory, _ = transport_fixture(
        monkeypatch,
        response=response,
        profile=profile,
    )

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is ArkOneShotFailureCode.RESPONSE_TOO_LARGE
    assert result.receipt.response_complete is False
    assert result.receipt.observed_response_bytes == 5
    assert result.receipt.observed_response_sha256 == hashlib.sha256(b"12345").hexdigest()
    assert response.read_calls == 1
    assert response.read_amounts == [5]
    assert factory.instances[0].request_calls == 1
    assert not hasattr(result, "response")


def test_nonidentity_content_encoding_is_terminal_without_read_or_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeHTTPResponse(headers={"Content-Encoding": "gzip"})
    transport, factory, _ = transport_fixture(monkeypatch, response=response)

    result = transport.send(request_fixture())

    assert isinstance(result, ArkOneShotTransportFailure)
    assert result.code is ArkOneShotFailureCode.RESPONSE_PROTOCOL_ERROR
    assert result.receipt.request_calls == result.receipt.getresponse_calls == 1
    assert result.receipt.body_read_calls == 0
    assert response.read_calls == 0
    assert factory.instances[0].request_calls == 1


def test_second_send_is_closed_before_credential_or_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, factory, lease = transport_fixture(monkeypatch)
    first = transport.send(request_fixture())
    second = transport.send(request_fixture())

    assert isinstance(first, ArkOneShotTransportSuccess)
    assert isinstance(second, ArkOneShotTransportFailure)
    assert second.code is ArkOneShotFailureCode.ALREADY_CONSUMED
    assert second.receipt.request_calls == second.receipt.connection_objects == 0
    assert lease.calls == 1
    assert len(factory.instances) == 1
    assert factory.instances[0].request_calls == 1


def test_concurrent_send_allows_exactly_one_request_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    transport, factory, lease = transport_fixture(
        monkeypatch,
        request_entered=entered,
        request_release=release,
    )
    results: list[object] = []

    worker = threading.Thread(target=lambda: results.append(transport.send(request_fixture())))
    worker.start()
    assert entered.wait(timeout=5)
    concurrent = transport.send(request_fixture())
    release.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert isinstance(concurrent, ArkOneShotTransportFailure)
    assert concurrent.code is ArkOneShotFailureCode.ALREADY_CONSUMED
    assert len(results) == 1 and isinstance(results[0], ArkOneShotTransportSuccess)
    assert lease.calls == 1
    assert len(factory.instances) == 1
    assert factory.instances[0].request_calls == 1


def test_source_has_one_request_callsite_and_no_general_http_or_environment_client() -> None:
    source_path = Path(transport_module.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    request_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "request"
    ]
    assert len(request_calls) == 1
    ancestor = parents.get(request_calls[0])
    while ancestor is not None:
        assert not isinstance(ancestor, (ast.For, ast.AsyncFor, ast.While))
        ancestor = parents.get(ancestor)

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {"os", "urllib", "urllib.request", "requests", "subprocess"} & imports
    assert "set_tunnel(" not in source
    assert "os.environ" not in source
