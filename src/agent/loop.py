"""The tool loop: the go-between for the LLM and the tools (phase 3.2).

1. Send the conversation and the tool definitions to Bedrock (Converse API).
2. Plain text back: done. Tool request back: run the tool, send the result, repeat.
3. Stop after MAX_TURNS model calls so a confused model cannot loop forever or run up cost.

A failing tool does not crash the session: the error goes back to the model as a tool result.
On the phone path Amazon Connect runs this loop itself; this file is the terminal version.
"""

import logging
import time
from dataclasses import dataclass

import boto3

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import TOOL_SPECS, run_tool

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
MAX_TURNS = 5
MAX_TOKENS = 1024
TEMPERATURE = 0.0
GIVE_UP_REPLY = "Sorry, I could not finish looking this up. Please try again or ask your academic advisor."

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolStep:
    tool: str
    input: dict
    ms: int
    status: str


@dataclass(frozen=True)
class TurnResult:
    reply: str
    messages: list[dict]
    trace: list[ToolStep]


def make_client():
    """The region comes from env.sh (AWS_REGION)."""
    return boto3.client("bedrock-runtime")


def _call_model(client, messages: list[dict]) -> dict:
    return client.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        toolConfig={"tools": [{"toolSpec": spec} for spec in TOOL_SPECS]},
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": TEMPERATURE},
    )


def _run_one(block: dict, student_id: str) -> tuple[dict, ToolStep]:
    """Runs one tool request and returns the toolResult block for the model plus a trace step."""
    request = block["toolUse"]
    started = time.perf_counter()
    try:
        content, status = [{"json": run_tool(request["name"], request["input"], student_id)}], "success"
    except Exception as error:  # any tool failure goes back to the model, never crashes the session
        log.warning("Tool %s failed: %s", request["name"], error)
        content, status = [{"text": f"Tool error: {error}"}], "error"
    ms = round((time.perf_counter() - started) * 1000)
    result = {"toolResult": {"toolUseId": request["toolUseId"], "content": content, "status": status}}
    return result, ToolStep(request["name"], request["input"], ms, status)


def _reply_text(message: dict) -> str:
    return "".join(block["text"] for block in message["content"] if "text" in block).strip()


def run_turn(history: list[dict], user_text: str, student_id: str, client) -> TurnResult:
    """Answers one student message. Returns the reply, the new conversation and the tool trace."""
    messages = [*history, {"role": "user", "content": [{"text": user_text}]}]
    trace: list[ToolStep] = []
    for _ in range(MAX_TURNS):
        response = _call_model(client, messages)
        message = response["output"]["message"]
        messages = [*messages, message]
        if response["stopReason"] != "tool_use":
            return TurnResult(_reply_text(message), messages, trace)
        outcomes = [_run_one(block, student_id) for block in message["content"] if "toolUse" in block]
        messages = [*messages, {"role": "user", "content": [result for result, _ in outcomes]}]
        trace = [*trace, *[step for _, step in outcomes]]
    log.warning("Stopped after %d model calls without a final answer", MAX_TURNS)
    return TurnResult(GIVE_UP_REPLY, messages, trace)
