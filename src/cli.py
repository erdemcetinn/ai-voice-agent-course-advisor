"""Chat with the advisor in the terminal (phase 3.4).

Usage:
    source env.sh
    python -m src.cli --student s001

The student ID comes from the command line, never from the model. Each tool call is shown with
its input and duration so you can see what the agent did. Type "exit" to quit.
"""

import argparse
import logging
import sys

from src.agent.loop import MODEL_ID, make_client, run_turn
from src.tools.transcript import StudentNotFoundError, load_student

EXIT_WORDS = {"exit", "quit"}


def _show_trace(trace) -> None:
    for step in trace:
        print(f"   [tool] {step.tool} {step.input or ''} ({step.ms} ms, {step.status})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--student", required=True, help="student ID, e.g. s001")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    try:
        name = load_student(args.student)["name"]
    except StudentNotFoundError as error:
        sys.exit(str(error))

    client = make_client()
    history: list[dict] = []
    print(f"Course advisor ({MODEL_ID}). Signed in as {name} ({args.student}). Type 'exit' to quit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in EXIT_WORDS:
            break
        if not text:
            continue
        result = run_turn(history, text, args.student, client)
        _show_trace(result.trace)
        print(f"advisor> {result.reply}\n")
        history = result.messages


if __name__ == "__main__":
    main()
