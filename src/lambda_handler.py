"""The single Lambda that runs all three tools for the phone path (phase 6.3).

Event for a manual test (aws lambda invoke):
    {"tool": "search_catalog", "input": {"query": "ITC 6680"}, "student_id": "s001"}

AgentCore Gateway (phase 7) passes the tool's arguments as the event and the tool name in the
client context. How exactly, and how the student ID reaches the tool without the model choosing
it, is still to be verified; _tool_name() already reads the documented client-context key.

Environment: DATA_BUCKET (catalog and index in S3), STUDENTS_TABLE (DynamoDB).
Data loads lazily and is cached, so only a cold start pays for reading it.
"""

import logging

from src.agent.tools import run_tool

GATEWAY_TOOL_KEY = "bedrockAgentCoreToolName"
GATEWAY_NAME_SEPARATOR = "___"  # Gateway sends "<target>___<tool>"

log = logging.getLogger()
log.setLevel(logging.INFO)


def _tool_name(event: dict, context) -> str:
    if "tool" in event:
        return event["tool"]
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    if GATEWAY_TOOL_KEY in custom:
        return custom[GATEWAY_TOOL_KEY].split(GATEWAY_NAME_SEPARATOR)[-1]
    raise ValueError("No tool name in the event or the client context")


def handler(event: dict, context) -> dict:
    try:
        name = _tool_name(event, context)
        tool_input = event.get("input", {})
        student_id = event.get("student_id", "")
        log.info("tool=%s input=%s", name, tool_input)
        return {"ok": True, "result": run_tool(name, tool_input, student_id)}
    except Exception as error:  # the caller gets a readable error instead of a Lambda crash
        log.exception("Tool call failed")
        return {"ok": False, "error": str(error)}
