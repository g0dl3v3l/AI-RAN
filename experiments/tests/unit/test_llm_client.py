from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RecordingTransport:
    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def __call__(self, *, url: str, payload: dict[str, object], timeout_s: float, api_key: str):
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "timeout_s": timeout_s,
                "api_key": api_key,
            }
        )
        return self.response


class FailingTransport:
    def __init__(self, error: Exception):
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, *, url: str, payload: dict[str, object], timeout_s: float, api_key: str):
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "timeout_s": timeout_s,
                "api_key": api_key,
            }
        )
        raise self.error



def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]



def test_smoke_request_writes_request_and_response(tmp_path: Path):
    from ai_runtime_experiments.workload import LLMSmokeClient

    transport = RecordingTransport(
        {
            "id": "chatcmpl-123",
            "model": "test-model",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "pong",
                    }
                }
            ],
        }
    )
    client = LLMSmokeClient(transport=transport, timeout_s=12.5, api_key="EMPTY")

    response_record = client.send_smoke_request(
        run_id="task-7",
        output_dir=tmp_path,
        base_url="http://localhost:8000/v1/",
        model="test-model",
        prompt="ping",
        request_id="req-123",
        max_tokens=16,
    )

    request_records = _read_jsonl(tmp_path / "smoke_request.jsonl")
    response_records = _read_jsonl(tmp_path / "smoke_response.jsonl")

    assert len(request_records) == 1
    assert len(response_records) == 1
    assert request_records[0]["request_id"] == "req-123"
    assert request_records[0]["status"] == "ok"
    assert request_records[0]["component"] == "smoke_request"
    assert request_records[0]["details"]["runtime"] == "vllm"
    assert request_records[0]["details"]["base_url"] == "http://localhost:8000/v1"
    assert request_records[0]["details"]["request_url"] == "http://localhost:8000/v1/chat/completions"
    assert request_records[0]["details"]["request"] == {
        "model": "test-model",
        "message_count": 1,
        "temperature": 0.0,
        "max_tokens": 16,
    }
    assert response_records[0]["request_id"] == "req-123"
    assert request_records[0]["payload"]["messages"][0]["content"] == "ping"
    assert response_record["status"] == "ok"
    assert response_record["component"] == "smoke_response"
    assert response_records[0]["component"] == "smoke_response"
    assert response_records[0]["details"]["runtime"] == "vllm"
    assert response_records[0]["details"]["base_url"] == "http://localhost:8000/v1"
    assert response_records[0]["details"]["request_url"] == "http://localhost:8000/v1/chat/completions"
    assert response_records[0]["details"]["request"] == {
        "model": "test-model",
        "message_count": 1,
        "temperature": 0.0,
        "max_tokens": 16,
    }
    assert response_records[0]["details"]["response"] == {
        "id": "chatcmpl-123",
        "model": "test-model",
        "choice_count": 1,
    }
    assert response_records[0]["details"]["extracted"] == {"assistant_text": "pong"}
    assert response_records[0]["response"]["choices"][0]["message"]["content"] == "pong"
    assert response_records[0]["extracted"]["assistant_text"] == "pong"
    assert transport.calls == [
        {
            "url": "http://localhost:8000/v1/chat/completions",
            "payload": request_records[0]["payload"],
            "timeout_s": 12.5,
            "api_key": "EMPTY",
        }
    ]



def test_transport_error_writes_error_response_record(tmp_path: Path):
    from ai_runtime_experiments.workload import LLMSmokeClient

    transport = FailingTransport(RuntimeError("boom"))
    client = LLMSmokeClient(transport=transport)

    response_record = client.send_smoke_request(
        run_id="task-7",
        output_dir=tmp_path,
        base_url="http://localhost:8000/v1",
        model="test-model",
        prompt="ping",
        request_id="req-error",
    )

    request_records = _read_jsonl(tmp_path / "smoke_request.jsonl")
    response_records = _read_jsonl(tmp_path / "smoke_response.jsonl")

    assert request_records[0]["request_id"] == "req-error"
    assert request_records[0]["status"] == "ok"
    assert request_records[0]["component"] == "smoke_request"
    assert request_records[0]["details"]["runtime"] == "vllm"
    assert request_records[0]["details"]["base_url"] == "http://localhost:8000/v1"
    assert request_records[0]["details"]["request_url"] == "http://localhost:8000/v1/chat/completions"
    assert request_records[0]["details"]["request"] == {
        "model": "test-model",
        "message_count": 1,
        "temperature": 0.0,
        "max_tokens": 64,
    }
    assert response_record["status"] == "error"
    assert response_record["component"] == "smoke_response"
    assert response_records[0]["request_id"] == "req-error"
    assert response_records[0]["component"] == "smoke_response"
    assert response_records[0]["details"]["runtime"] == "vllm"
    assert response_records[0]["details"]["base_url"] == "http://localhost:8000/v1"
    assert response_records[0]["details"]["request_url"] == "http://localhost:8000/v1/chat/completions"
    assert response_records[0]["details"]["request"] == {
        "model": "test-model",
        "message_count": 1,
        "temperature": 0.0,
        "max_tokens": 64,
    }
    assert response_records[0]["details"]["response"] == {
        "id": None,
        "model": None,
        "choice_count": 0,
    }
    assert response_records[0]["details"]["extracted"] == {"assistant_text": None}
    assert response_records[0]["details"]["reason"] == "boom"
    assert response_records[0]["error_type"] == "RuntimeError"
    assert response_records[0]["error_message"] == "boom"
