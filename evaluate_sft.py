"""Evaluate the fixed SFT endpoint using the shared sequential conversation harness."""
import json
from pathlib import Path
from types import SimpleNamespace

from evaluate import greedy, run_case
from verify_dialogue import score_probe

DEVELOPMENT = Path(__file__).parent / "reports/dialogue-readiness/conversation-dev-v1.jsonl"
DEV_SHA = "6b954fb54d2520a43b2f342f2a6968f773b41429645866c93a9b5d0549f04535"


def evaluate(model, tokenizer, check):
    model.eval()
    guard = SimpleNamespace(check=check)

    def generate(prefix, budget):
        return greedy(model, prefix, budget, guard)

    probe = score_probe(tokenizer, generate)
    transcripts = [run_case(json.loads(line), generate, tokenizer) for line in DEVELOPMENT.open()]
    return dict(probe=probe, development=transcripts, decoding="raw greedy, complete JSON, no repair or retry",
                gate="at least 16/20 both-members passes per probe skill; complete conversations require adjudication")
