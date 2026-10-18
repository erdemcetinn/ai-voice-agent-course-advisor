"""The single Lambda that runs all three tools for the phone path (phase 6.3).

Event for a manual test (aws lambda invoke):
    {"tool": "search_catalog", "input": {"query": "ITC 6680"}, "student_id": "s001"}

Event from AgentCore Gateway (phase 7): the tool's arguments themselves, e.g. {"query": "ITC 6680"},
with the tool name in context.client_context.custom["bedrockAgentCoreToolName"] as "<target>___<tool>".
The gateway tool schemas declare student_id; Connect pins it with "override input values" so the
model never chooses it. It is taken out of the arguments before the tool runs.

Environment: DATA_BUCKET (catalog and index in S3), STUDENTS_TABLE (DynamoDB).
Data loads lazily and is cached, so only a cold start pays for reading it.
"""

import logging

from src.agent.tools import run_tool

GATEWAY_TOOL_KEY = "bedrockAgentCoreToolName"
GATEWAY_NAME_SEPARATOR = "___"  # Gateway sends "<target>___<tool>"

log = logging.getLogger()
log.setLevel(logging.INFO)


def _parse(event: dict, context) -> tuple[str, dict, str]:
    """(tool name, tool arguments, student_id) for a manual test event or a Gateway call."""
    if "tool" in event:
        return event["tool"], event.get("input", {}), event.get("student_id", "")
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    if GATEWAY_TOOL_KEY not in custom:
        raise ValueError("No tool name in the event or the client context")
    name = custom[GATEWAY_TOOL_KEY].split(GATEWAY_NAME_SEPARATOR)[-1]
    arguments = {key: value for key, value in event.items() if key != "student_id"}
    return name, arguments, event.get("student_id", "")


def handler(event: dict, context) -> dict:
    try:
        name, tool_input, student_id = _parse(event, context)
        log.info("tool=%s input=%s student=%s", name, tool_input, student_id)
        return {"ok": True, "result": run_tool(name, tool_input, student_id)}
    except Exception as error:  # the caller gets a readable error instead of a Lambda crash
        log.exception("Tool call failed")
        return {"ok": False, "error": str(error)}
