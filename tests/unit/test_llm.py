"""Unit tests for the Claude wrapper, using a fake client (no network, no API key)."""

import json
from types import SimpleNamespace

import pytest

from rse.common.llm import ClaudeClient, ModelSpec, cost_usd

CONFIG = """
[models.bulk]
model_id = "test-haiku"
max_tokens = 64
input_per_mtok = 1.0
output_per_mtok = 5.0

[models.judge]
model_id = "REPLACE_WITH_SONNET_MODEL_ID"
"""


class FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="OK")],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
            model=kwargs["model"],
            stop_reason="end_turn",
            _request_id="req_test",
        )


@pytest.fixture
def client(tmp_path):
    config = tmp_path / "models.toml"
    config.write_text(CONFIG)
    fake = SimpleNamespace(messages=FakeMessages())
    return ClaudeClient(config_path=config, log_path=tmp_path / "calls.jsonl", client=fake)


def test_cost_usd() -> None:
    spec = ModelSpec("bulk", "m", input_per_mtok=1.0, output_per_mtok=5.0)
    assert cost_usd(spec, 1_000_000, 100_000) == pytest.approx(1.5)
    assert cost_usd(ModelSpec("bulk", "m"), 10, 10) is None


def test_complete_returns_text_usage_and_cost(client) -> None:
    result = client.complete("bulk", "Say OK", purpose="unit-test")
    assert result.text == "OK"
    assert (result.input_tokens, result.output_tokens) == (1000, 200)
    assert result.cost_usd == pytest.approx(0.002)
    call = client._client.messages.calls[0]
    assert call["model"] == "test-haiku"
    assert call["max_tokens"] == 64


def test_log_has_usage_but_no_prompt_text(client) -> None:
    client.complete("bulk", "secret prompt text", purpose="unit-test", run_id="r1")
    line = client.log_path.read_text().strip()
    record = json.loads(line)
    assert record["purpose"] == "unit-test"
    assert record["run_id"] == "r1"
    assert record["input_tokens"] == 1000
    assert "secret prompt text" not in line
    assert "text" not in record


def test_unconfigured_alias_fails_clearly(client) -> None:
    with pytest.raises(RuntimeError, match="no model_id"):
        client.complete("judge", "hi")
    with pytest.raises(KeyError):
        client.complete("missing", "hi")
