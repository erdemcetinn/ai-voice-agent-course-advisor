"""Tests for src/lambda_handler.py and src/data.py. No AWS: data comes from the local files."""

from types import SimpleNamespace

import src.data as data
from src.lambda_handler import handler


def test_manual_event_runs_the_tool():
    response = handler({"tool": "search_catalog", "input": {"query": "ITC 6680"}, "student_id": "s001"}, None)
    assert response["ok"] is True
    assert response["result"]["results"][0]["title"] == "CISSP Preparation"


def _gateway(tool: str) -> SimpleNamespace:
    return SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"advisor-tools___{tool}"}))


def test_gateway_call_passes_arguments_directly():
    response = handler({"student_id": "s002"}, _gateway("get_transcript"))
    assert response["result"]["student_id"] == "s002"


def test_gateway_arguments_reach_the_tool_without_student_id():
    response = handler({"course_code": "ITC 6680", "student_id": "s001"}, _gateway("plan_next_semester"))
    assert response["result"]["missing_prerequisites"] == "ITC 6620"


def test_gateway_search_has_no_student_id():
    response = handler({"query": "ITC 6680"}, _gateway("search_catalog"))
    assert response["result"]["mode"] == "exact"


def test_errors_are_returned_not_raised():
    response = handler({"tool": "nope", "student_id": "s001"}, None)
    assert response == {"ok": False, "error": "Unknown tool: nope"}


def test_missing_tool_name_is_an_error():
    assert handler({"input": {}}, None)["ok"] is False


def test_data_file_downloads_from_s3_once(monkeypatch, tmp_path):
    downloads = []

    class FakeS3:
        def download_file(self, bucket, key, target):
            downloads.append((bucket, key))
            open(target, "w").write("{}")

    monkeypatch.setenv("DATA_BUCKET", "my-bucket")
    monkeypatch.setattr(data, "LAMBDA_TMP_DIR", tmp_path)
    monkeypatch.setattr(data.boto3, "client", lambda service: FakeS3())
    first = data.data_file("catalog.json")
    second = data.data_file("catalog.json")
    assert first == second == tmp_path / "catalog.json"
    assert downloads == [("my-bucket", "catalog.json")]
