"""Tests for src/agent (tool definitions, dispatch and the tool loop). Uses a scripted fake Bedrock client."""

import pytest

from src.agent.loop import MAX_TURNS, run_turn
from src.agent.tools import TOOL_SPECS, run_tool


class TestToolSpecs:
    def test_every_tool_has_name_description_and_schema(self):
        for spec in TOOL_SPECS:
            assert spec["name"] and spec["description"]
            assert spec["inputSchema"]["json"]["type"] == "object"

    def test_get_transcript_has_no_student_id_parameter(self):
        spec = next(s for s in TOOL_SPECS if s["name"] == "get_transcript")
        assert spec["inputSchema"]["json"]["properties"] == {}


class TestRunTool:
    def test_get_transcript_uses_the_session_student(self):
        assert run_tool("get_transcript", {}, student_id="s002")["student_id"] == "s002"

    def test_get_transcript_ignores_an_id_the_model_tries_to_pass(self):
        assert run_tool("get_transcript", {"student_id": "s003"}, student_id="s001")["student_id"] == "s001"

    def test_search_catalog_passes_the_query(self):
        assert run_tool("search_catalog", {"query": "ITC 6680"}, student_id="s001")["mode"] == "exact"

    def test_plan_next_semester_uses_the_session_student(self):
        assert run_tool("plan_next_semester", {"course_code": "ITC 6680", "student_id": "s003"}, student_id="s001")["missing_prerequisites"] == "ITC 6620"

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            run_tool("delete_everything", {}, student_id="s001")


def _text(text: str) -> dict:
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}, "stopReason": "end_turn"}


def _tool_use(name: str, tool_input: dict, tool_use_id: str = "t1") -> dict:
    block = {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": tool_input}}
    return {"output": {"message": {"role": "assistant", "content": [block]}}, "stopReason": "tool_use"}


class FakeBedrock:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.requests: list[dict] = []

    def converse(self, **request) -> dict:
        self.requests = [*self.requests, request]
        return self.responses[len(self.requests) - 1]


class TestRunTurn:
    def test_plain_answer_needs_one_call(self):
        client = FakeBedrock([_text("Hello!")])
        result = run_turn([], "Hi", "s001", client)
        assert result.reply == "Hello!"
        assert result.trace == []
        assert [m["role"] for m in result.messages] == ["user", "assistant"]

    def test_tool_request_is_run_and_result_sent_back(self):
        client = FakeBedrock([_tool_use("get_transcript", {}), _text("You have 6 credits.")])
        result = run_turn([], "How many credits do I have?", "s001", client)
        assert result.reply == "You have 6 credits."
        assert [step.tool for step in result.trace] == ["get_transcript"]
        tool_result = client.requests[1]["messages"][-1]["content"][0]["toolResult"]
        assert tool_result["toolUseId"] == "t1"
        assert tool_result["status"] == "success"
        assert tool_result["content"][0]["json"]["credits_completed"] == 6

    def test_tool_error_is_sent_to_the_model_instead_of_crashing(self):
        client = FakeBedrock([_tool_use("search_catalog", {"query": "  "}), _text("Sorry, I could not search.")])
        result = run_turn([], "search nothing", "s001", client)
        tool_result = client.requests[1]["messages"][-1]["content"][0]["toolResult"]
        assert tool_result["status"] == "error"
        assert result.trace[0].status == "error"
        assert result.reply == "Sorry, I could not search."

    def test_stops_after_max_turns(self):
        client = FakeBedrock([_tool_use("get_transcript", {}, f"t{i}") for i in range(MAX_TURNS + 1)])
        result = run_turn([], "loop forever", "s001", client)
        assert len(client.requests) == MAX_TURNS
        assert "advisor" in result.reply

    def test_history_is_not_mutated(self):
        history = [{"role": "user", "content": [{"text": "earlier"}]}, {"role": "assistant", "content": [{"text": "ok"}]}]
        before = [dict(m) for m in history]
        run_turn(history, "Hi", "s001", FakeBedrock([_text("Hello!")]))
        assert history == before

    def test_request_contains_system_prompt_tools_and_model(self):
        client = FakeBedrock([_text("Hello!")])
        run_turn([], "Hi", "s001", client)
        request = client.requests[0]
        assert "haiku" in request["modelId"]
        assert request["system"][0]["text"]
        assert {t["toolSpec"]["name"] for t in request["toolConfig"]["tools"]} == {"get_transcript", "search_catalog", "plan_next_semester"}
