"""A deterministic in-memory provider for VFPS M0 fault tests.

This module deliberately does not import environment, networking, HTTP, shell,
or subprocess facilities.  A real provider belongs behind a later human gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Protocol

from .contracts import AttemptStart, AttemptStatus


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Ephemeral provider output; response_text must never be written to ledgers."""

    status: AttemptStatus
    completed_unix_ms: int
    response_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_response_id: str | None = None
    provider_response_id_sha256: str | None = None
    observed_model_hash: str | None = None
    error_code: str | None = None
    late: bool = False


class AccuracyProvider(Protocol):
    """One-shot provider interface consumed by the formal accuracy runner."""

    def invoke(self, request_bytes: bytes, attempt: AttemptStart) -> ProviderResponse: ...


class MockProvider:
    """A deterministic, dependency-free stand-in for one physical request."""

    def __init__(
        self,
        *,
        response_text: str | None,
        status: AttemptStatus = AttemptStatus.SUCCESS,
        completion_offset_ms: int = 1,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        provider_response_id: str | None = None,
        observed_model_hash: str | None = None,
        error_code: str | None = None,
        force_late: bool = False,
        before_return: Callable[[AttemptStart], None] | None = None,
    ) -> None:
        if completion_offset_ms < 0:
            raise ValueError("completion_offset_ms must be non-negative")
        self._response_text = response_text
        self._status = status
        self._completion_offset_ms = completion_offset_ms
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._provider_response_id = provider_response_id
        self._observed_model_hash = observed_model_hash
        self._error_code = error_code
        self._force_late = force_late
        self._before_return = before_return
        self._physical_attempts = 0
        self._last_request_sha256: str | None = None

    @property
    def physical_attempts(self) -> int:
        return self._physical_attempts

    @property
    def last_request_sha256(self) -> str | None:
        return self._last_request_sha256

    def invoke(self, request_bytes: bytes, attempt: AttemptStart) -> ProviderResponse:
        if not isinstance(request_bytes, bytes):
            raise TypeError("provider request must be canonical bytes")
        self._physical_attempts += 1
        self._last_request_sha256 = hashlib.sha256(request_bytes).hexdigest()
        if self._before_return is not None:
            self._before_return(attempt)
        completed = attempt.started_unix_ms + self._completion_offset_ms
        late = self._force_late or completed > attempt.deadline_unix_ms
        return ProviderResponse(
            status=self._status,
            completed_unix_ms=completed,
            response_text=self._response_text,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            provider_response_id=self._provider_response_id,
            observed_model_hash=self._observed_model_hash,
            error_code=self._error_code,
            late=late,
        )
