"""Runs the evaluation set against the agent and writes a report (phase 4.2).

Usage:
    source env.sh
    python -m evals.run_evals --label baseline --runs 3

Each question is asked --runs times, each time in a fresh conversation, to measure consistency
as well as accuracy. Results go to evals/results/<label>.json (every answer) and <label>.md (summary).
"""

import argparse
import json
import logging
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import boto3
from botocore.config import Config

from evals.judge import judge
from src.agent.loop import MODEL_ID, run_turn

EVALS_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVALS_DIR / "questions.jsonl"
RESULTS_DIR = EVALS_DIR / "results"
WORKERS = 4
P90 = 0.9
RETRY_CONFIG = Config(retries={"max_attempts": 8, "mode": "adaptive"})
REQUIRED_FIELDS = {"id", "category", "student", "q", "expect"}

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Attempt:
    id: str
    category: str
    run: int
    answer: str
    tools: list[str]
    seconds: float
    correct: bool
    reason: str


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    questions = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for question in questions:
        missing = REQUIRED_FIELDS - question.keys()
        if missing:
            raise ValueError(f"Question {question.get('id', '?')} is missing fields: {sorted(missing)}")
    ids = [question["id"] for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Question ids must be unique")
    return questions


def ask(question: dict, run: int, agent_client, judge_client) -> Attempt:
    started = time.perf_counter()
    result = run_turn([], question["q"], question["student"], agent_client)
    seconds = round(time.perf_counter() - started, 2)
    verdict = judge(question, result.reply, judge_client)
    return Attempt(question["id"], question["category"], run, result.reply,
                   [step.tool for step in result.trace], seconds, verdict["correct"], verdict["reason"])


def summarize(attempts: list[Attempt]) -> dict:
    """Accuracy overall and per category, consistency per question, latency."""
    by_question: dict[str, list[Attempt]] = {}
    for attempt in attempts:
        by_question = {**by_question, attempt.id: [*by_question.get(attempt.id, []), attempt]}
    categories = sorted({attempt.category for attempt in attempts})
    seconds = sorted(attempt.seconds for attempt in attempts)
    return {
        "attempts": len(attempts),
        "correct": sum(attempt.correct for attempt in attempts),
        "by_category": {
            category: (sum(a.correct for a in attempts if a.category == category),
                       sum(1 for a in attempts if a.category == category))
            for category in categories
        },
        "always_right": sorted(q for q, runs in by_question.items() if all(a.correct for a in runs)),
        "always_wrong": sorted(q for q, runs in by_question.items() if not any(a.correct for a in runs)),
        "inconsistent": sorted(q for q, runs in by_question.items() if 0 < sum(a.correct for a in runs) < len(runs)),
        "median_seconds": statistics.median(seconds) if seconds else 0.0,
        "p90_seconds": seconds[math.ceil(P90 * len(seconds)) - 1] if seconds else 0.0,  # nearest-rank
    }


def render_markdown(label: str, summary: dict, attempts: list[Attempt], runs: int) -> str:
    pct = 100 * summary["correct"] / summary["attempts"]
    lines = [
        f"# Evaluation: {label}",
        "",
        f"Agent model: `{MODEL_ID}`. Each question asked {runs} times in a fresh conversation.",
        "",
        f"**Accuracy: {summary['correct']} / {summary['attempts']} ({pct:.0f}%)**",
        f"Median latency {summary['median_seconds']:.1f} s, p90 {summary['p90_seconds']:.1f} s.",
        "",
        "| Category | Correct |",
        "|---|---|",
        *[f"| {category} | {ok} / {total} |" for category, (ok, total) in summary["by_category"].items()],
        "",
        f"Inconsistent (right in some runs, wrong in others): {', '.join(summary['inconsistent']) or 'none'}",
        f"Always wrong: {', '.join(summary['always_wrong']) or 'none'}",
        "",
        "## Wrong answers",
        "",
    ]
    for attempt in sorted((a for a in attempts if not a.correct), key=lambda a: (a.id, a.run)):
        lines += [f"**{attempt.id} run {attempt.run}** ({attempt.category}): {attempt.reason}", "",
                  f"> {attempt.answer.replace(chr(10), ' ')}", ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True, help="name of the result files, e.g. baseline")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", nargs="*", help="question ids to run (default: all)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    questions = [q for q in load_questions() if not args.only or q["id"] in args.only]
    client = boto3.client("bedrock-runtime", config=RETRY_CONFIG)
    jobs = [(question, run) for question in questions for run in range(1, args.runs + 1)]
    log.info("Asking %d questions x %d runs = %d attempts...", len(questions), args.runs, len(jobs))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        attempts = list(pool.map(lambda job: ask(job[0], job[1], client, client), jobs))

    summary = summarize(attempts)
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"{args.label}.json").write_text(
        json.dumps({"summary": summary, "attempts": [asdict(a) for a in attempts]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    report = RESULTS_DIR / f"{args.label}.md"
    report.write_text(render_markdown(args.label, summary, attempts, args.runs), encoding="utf-8")
    log.info("Accuracy %d / %d. Inconsistent: %s. Report: %s",
             summary["correct"], summary["attempts"], summary["inconsistent"] or "none", report.relative_to(EVALS_DIR.parent))


if __name__ == "__main__":
    main()
