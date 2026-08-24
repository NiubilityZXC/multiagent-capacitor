"""Safe subprocess adapter for the Volcengine AgentPlan Responses API.

No credential is accepted as a constructor argument or command-line flag.  A
real call requires ARK_API_KEY and ARK_BASE_URL in the process environment.
Dry-run uses a non-secret placeholder when those variables are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence

from .orchestrator import ProviderResult, canonical_prompt


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ArkcliConfig:
    model: str = "kimi-k3"
    dry_run: bool = True
    timeout_seconds: float = 90.0
    max_network_retries: int = 1
    max_output_tokens: int = 512
    temperature: str = "0"
    top_p: str = "1"


class ArkcliAgentProvider:
    def __init__(self, config: ArkcliConfig | None = None, *, runner: Runner = subprocess.run) -> None:
        self.config = config or ArkcliConfig()
        self._runner = runner

    @staticmethod
    def _redact(text: str, secret: str | None) -> str:
        result = text
        if secret:
            result = result.replace(secret, "[REDACTED]")
        return result[:4000]

    def _child_environment(self) -> tuple[dict[str, str], str | None]:
        environment = dict(os.environ)
        key = environment.get("ARK_API_KEY")
        base_url = environment.get("ARK_BASE_URL")
        if self.config.dry_run:
            environment.setdefault("ARK_API_KEY", "dry-run-placeholder")
            environment.setdefault(
                "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/plan/v3"
            )
        elif not key or not base_url:
            raise RuntimeError("real AgentPlan calls require ARK_API_KEY and ARK_BASE_URL")
        environment.update(
            {
                "ARKCLI_CALLER_TYPE": "ai_agent",
                "ARKCLI_CALLER_NAME": "codex",
                "ARKCLI_SKILL_NAME": "arkcli-chat",
            }
        )
        return environment, key

    def _argv(
        self,
        *,
        role: str,
        prompt: str,
        schema_path: Path,
        instructions: str,
    ) -> list[str]:
        argv = [
            "arkcli",
            "+chat",
            "--model",
            self.config.model,
            "--instructions",
            instructions,
            "--max-output-tokens",
            str(self.config.max_output_tokens),
            "--temperature",
            self.config.temperature,
            "--top-p",
            self.config.top_p,
            "--caching",
            "disabled",
            "--thinking",
            "disabled",
            "--text-format",
            "json_schema",
            "--text-schema",
            str(schema_path),
            "--text-schema-name",
            f"capacitor_{role}",
            "--text-strict",
            "--tool-choice",
            "none",
            "--no-progress",
        ]
        if self.config.dry_run:
            argv.append("--dry-run")
        argv.append(prompt)
        return argv

    def invoke(
        self,
        *,
        role: str,
        payload: Mapping[str, Any],
        json_schema: Mapping[str, Any],
        instructions: str,
    ) -> ProviderResult:
        environment, original_secret = self._child_environment()
        prompt = canonical_prompt(payload)
        with tempfile.TemporaryDirectory(prefix="cap-agent-schema-") as temp_dir:
            schema_path = Path(temp_dir) / "response.schema.json"
            schema_path.write_text(
                json.dumps(json_schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                encoding="utf-8",
            )
            argv = self._argv(
                role=role,
                prompt=prompt,
                schema_path=schema_path,
                instructions=instructions,
            )
            # A credential must never be visible in argv, prompt, or schema.
            if original_secret and any(original_secret in item for item in argv):
                raise RuntimeError("credential unexpectedly entered subprocess argv")

            attempts = 1 + max(0, int(self.config.max_network_retries))
            for attempt in range(attempts):
                started = time.monotonic()
                try:
                    completed = self._runner(
                        argv,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=self.config.timeout_seconds,
                        check=False,
                        shell=False,
                    )
                except subprocess.TimeoutExpired:
                    if attempt + 1 < attempts:
                        continue
                    return ProviderResult(
                        status="ERROR",
                        decision=None,
                        latency_ms=(time.monotonic() - started) * 1000.0,
                        error_code="TIMEOUT",
                    )
                latency_ms = (time.monotonic() - started) * 1000.0
                stdout = self._redact(completed.stdout or "", original_secret)
                stderr = self._redact(completed.stderr or "", original_secret)
                if completed.returncode != 0:
                    retryable = any(
                        marker in stderr.lower()
                        for marker in ("429", "rate limit", "500", "502", "503", "504")
                    )
                    if retryable and attempt + 1 < attempts:
                        continue
                    return ProviderResult(
                        status="ERROR",
                        decision=None,
                        latency_ms=latency_ms,
                        error_code="RETRYABLE_NETWORK" if retryable else "CLI_FAILURE",
                    )
                try:
                    response = json.loads(stdout)
                except json.JSONDecodeError:
                    return ProviderResult(
                        status="ERROR",
                        decision=None,
                        latency_ms=latency_ms,
                        error_code="INVALID_CLI_JSON",
                    )
                if self.config.dry_run:
                    if response.get("schema_version") != "preview.v1" or not response.get("dry_run"):
                        return ProviderResult(
                            status="ERROR",
                            decision=None,
                            latency_ms=latency_ms,
                            error_code="INVALID_DRY_RUN_PREVIEW",
                        )
                    return ProviderResult(
                        status="DRY_RUN",
                        decision=None,
                        model=self.config.model,
                        latency_ms=latency_ms,
                    )
                content = response.get("content")
                if not isinstance(content, str):
                    return ProviderResult(
                        status="ERROR",
                        decision=None,
                        latency_ms=latency_ms,
                        error_code="MISSING_CONTENT",
                    )
                try:
                    decision = json.loads(content)
                except json.JSONDecodeError:
                    return ProviderResult(
                        status="ERROR",
                        decision=None,
                        latency_ms=latency_ms,
                        error_code="INVALID_DECISION_JSON",
                    )
                response_id = response.get("id")
                response_id_hash = (
                    hashlib.sha256(str(response_id).encode("utf-8")).hexdigest()
                    if response_id is not None
                    else None
                )
                usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else None
                # reasoning_content and the raw response are intentionally discarded.
                safe_usage = dict(usage) if usage is not None else None
                if safe_usage is not None and response_id_hash is not None:
                    safe_usage["response_id_sha256"] = response_id_hash
                return ProviderResult(
                    status="OK",
                    decision=decision if isinstance(decision, Mapping) else None,
                    model=str(response.get("model") or self.config.model),
                    usage=safe_usage,
                    latency_ms=latency_ms,
                )
        raise AssertionError("unreachable")
