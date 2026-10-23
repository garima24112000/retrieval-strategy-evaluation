"""Check that both Claude models answer through the RSE wrapper (RSE-17).

Usage:
    uv run python scripts/llm_smoke.py --list   # show model IDs your API key can use
    uv run python scripts/llm_smoke.py          # one tiny call to each alias
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from rse.common.llm import ClaudeClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="list available model IDs and exit")
    parser.add_argument("--aliases", nargs="+", default=["bulk", "judge"])
    args = parser.parse_args()

    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or key.startswith("replace-with"):
        print("ANTHROPIC_API_KEY is not set in .env. Create a key in the Claude Console first.")
        return 2

    client = ClaudeClient()
    if args.list:
        for model in client._client.models.list():
            print(f"{model.id}\t{getattr(model, 'display_name', '')}")
        return 0

    total = 0.0
    for alias in args.aliases:
        try:
            r = client.complete(
                alias, "Reply with exactly the word OK.", purpose="smoke", max_tokens=10
            )
        except RuntimeError as exc:
            print(exc)
            return 2
        cost = "n/a" if r.cost_usd is None else f"${r.cost_usd:.6f}"
        print(
            f"{alias:6} {r.model_id:32} text={r.text!r:8} in={r.input_tokens:<4} "
            f"out={r.output_tokens:<3} cost={cost} latency={r.latency_ms}ms"
        )
        total += r.cost_usd or 0.0
    print(f"total cost: ${total:.6f}  (log: {client.log_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
