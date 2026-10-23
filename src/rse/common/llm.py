"""Claude client wrapper: model aliases, retries, and token and cost logging (RSE-17).

Every call is appended to a JSONL log (default experiments/llm_calls.jsonl, git-ignored)
with tokens, cost, latency and purpose. Prompt text is never logged; only a short hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

DEFAULT_CONFIG = Path("configs/models.toml")
DEFAULT_LOG = Path("experiments/llm_calls.jsonl")
PLACEHOLDER_PREFIX = "REPLACE_WITH"


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    model_id: str
    max_tokens: int = 1024
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.model_id) and not self.model_id.startswith(PLACEHOLDER_PREFIX)


@dataclass(frozen=True)
class LLMResult:
    text: str
    alias: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_ms: float
    stop_reason: str | None
    request_id: str | None


def load_models(path: Path | str = DEFAULT_CONFIG) -> dict[str, ModelSpec]:
    """Read model aliases from a TOML file."""
    data = tomllib.loads(Path(path).read_text())
    return {
        alias: ModelSpec(alias=alias, **fields) for alias, fields in data.get("models", {}).items()
    }


def cost_usd(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float | None:
    """Cost of one call in USD, or None if prices are not configured."""
    if spec.input_per_mtok is None or spec.output_per_mtok is None:
        return None
    return round(
        (input_tokens * spec.input_per_mtok + output_tokens * spec.output_per_mtok) / 1_000_000, 6
    )


def _prompt_hash(system: str | None, prompt: str) -> str:
    return hashlib.sha256(f"{system or ''}\x00{prompt}".encode()).hexdigest()[:16]


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK.

    Retries: the SDK retries connection errors, 408/409/429 and 5xx responses with
    exponential backoff, up to ``max_retries`` times. ``timeout`` is per request, in seconds.
    """

    def __init__(
        self,
        config_path: Path | str = DEFAULT_CONFIG,
        log_path: Path | str | None = None,
        client: Any | None = None,
        max_retries: int = 3,
        timeout: float = 60.0,
    ) -> None:
        load_dotenv()
        self.models = load_models(config_path)
        self.log_path = Path(log_path or os.environ.get("RSE_LLM_LOG", DEFAULT_LOG))
        if client is None:
            import anthropic

            client = anthropic.Anthropic(max_retries=max_retries, timeout=timeout)
        self._client = client

    def spec(self, alias: str) -> ModelSpec:
        if alias not in self.models:
            raise KeyError(f"Unknown model alias {alias!r}; known: {sorted(self.models)}")
        spec = self.models[alias]
        if not spec.is_configured:
            raise RuntimeError(f"Model alias {alias!r} has no model_id yet; set it in models.toml")
        return spec

    def complete(
        self,
        alias: str,
        prompt: str,
        *,
        system: str | None = None,
        purpose: str = "adhoc",
        max_tokens: int | None = None,
        run_id: str | None = None,
    ) -> LLMResult:
        """Send one user message and return the text plus usage, cost and latency."""
        spec = self.spec(alias)
        kwargs: dict[str, Any] = {
            "model": spec.model_id,
            "max_tokens": max_tokens or spec.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        start = time.perf_counter()
        response = self._client.messages.create(**kwargs)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)

        text = "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        usage = response.usage
        result = LLMResult(
            text=text,
            alias=alias,
            model_id=getattr(response, "model", spec.model_id),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost_usd(spec, usage.input_tokens, usage.output_tokens),
            latency_ms=latency_ms,
            stop_reason=getattr(response, "stop_reason", None),
            request_id=getattr(response, "_request_id", None),
        )
        self._log(result, purpose=purpose, run_id=run_id, prompt_hash=_prompt_hash(system, prompt))
        return result

    def _log(
        self, result: LLMResult, *, purpose: str, run_id: str | None, prompt_hash: str
    ) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "run_id": run_id,
            "purpose": purpose,
            "prompt_hash": prompt_hash,
            **{k: v for k, v in asdict(result).items() if k != "text"},
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
