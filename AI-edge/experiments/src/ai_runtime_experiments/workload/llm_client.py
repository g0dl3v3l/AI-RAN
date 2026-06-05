from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol
from urllib import request

from ai_runtime_experiments.artifacts import append_jsonl
from ai_runtime_experiments.schemas import SCHEMA_VERSION, ProbeStatus
from ai_runtime_experiments.utils.time import monotonic_ns, utc_now_iso_z


class ChatCompletionTransport(Protocol):
    def __call__(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_s: float,
        api_key: str,
    ) -> dict[str, Any]: ...



def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("base_url must be non-empty")
    return normalized



def _chat_completions_url(base_url: str) -> str:
    return f"{_normalize_base_url(base_url)}/chat/completions"



def _coerce_messages(
    *,
    prompt: str | None,
    messages: Sequence[Mapping[str, str]] | None,
) -> list[dict[str, str]]:
    if messages is not None:
        return [dict(message) for message in messages]
    if prompt is None:
        raise ValueError("prompt or messages must be provided")
    return [{"role": "user", "content": prompt}]



def _extract_assistant_text(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices")
    if not isinstance(choices, Sequence) or not choices:
        return None

    first = choices[0]
    if not isinstance(first, Mapping):
        return None
    message = first.get("message")
    if not isinstance(message, Mapping):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    return None



def _status_from_exception(error: Exception) -> ProbeStatus:
    if isinstance(error, TimeoutError):
        return ProbeStatus.TIMEOUT
    return ProbeStatus.ERROR



def _smoke_request_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_messages = payload.get("messages")
    message_count = 0
    if isinstance(raw_messages, Sequence) and not isinstance(raw_messages, (str, bytes, bytearray)):
        message_count = len(raw_messages)

    return {
        "model": payload.get("model"),
        "message_count": message_count,
        "temperature": payload.get("temperature"),
        "max_tokens": payload.get("max_tokens"),
    }



def _smoke_response_summary(response: Mapping[str, Any] | None) -> dict[str, Any]:
    if response is None:
        return {
            "id": None,
            "model": None,
            "choice_count": 0,
        }

    raw_choices = response.get("choices")
    choice_count = 0
    if isinstance(raw_choices, Sequence) and not isinstance(raw_choices, (str, bytes, bytearray)):
        choice_count = len(raw_choices)

    return {
        "id": response.get("id"),
        "model": response.get("model"),
        "choice_count": choice_count,
    }



def _smoke_record_details(
    *,
    runtime: str,
    base_url: str,
    request_url: str,
    request_summary: Mapping[str, Any],
    response_summary: Mapping[str, Any] | None = None,
    extracted: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "runtime": runtime,
        "base_url": base_url,
        "request_url": request_url,
        "request": dict(request_summary),
    }
    if response_summary is not None:
        details["response"] = dict(response_summary)
    if extracted is not None:
        details["extracted"] = dict(extracted)
    if reason is not None:
        details["reason"] = reason
    return details



def post_openai_chat_completion(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_s: float,
    api_key: str,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_s) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)



class LLMSmokeClient:
    def __init__(
        self,
        *,
        transport: ChatCompletionTransport | None = None,
        timeout_s: float = 30.0,
        api_key: str = "EMPTY",
    ) -> None:
        self.transport = transport or post_openai_chat_completion
        self.timeout_s = timeout_s
        self.api_key = api_key

    def send_smoke_request(
        self,
        *,
        run_id: str,
        output_dir: str | Path,
        base_url: str,
        model: str,
        prompt: str | None = None,
        messages: Sequence[Mapping[str, str]] | None = None,
        request_id: str | None = None,
        runtime: str = "vllm",
        temperature: float = 0.0,
        max_tokens: int = 64,
    ) -> dict[str, Any]:
        request_identifier = request_id or uuid.uuid4().hex
        normalized_base_url = _normalize_base_url(base_url)
        request_url = _chat_completions_url(normalized_base_url)
        payload = {
            "model": model,
            "messages": _coerce_messages(prompt=prompt, messages=messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request_summary = _smoke_request_summary(payload)
        request_record = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "request_id": request_identifier,
            "runtime": runtime,
            "base_url": normalized_base_url,
            "status": ProbeStatus.OK.value,
            "component": "smoke_request",
            "timestamp_utc": utc_now_iso_z(),
            "monotonic_ns": monotonic_ns(),
            "payload": payload,
            "details": _smoke_record_details(
                runtime=runtime,
                base_url=normalized_base_url,
                request_url=request_url,
                request_summary=request_summary,
            ),
        }
        append_jsonl(Path(output_dir) / "smoke_request.jsonl", request_record)

        try:
            response_payload = self.transport(
                url=request_url,
                payload=payload,
                timeout_s=self.timeout_s,
                api_key=self.api_key,
            )
            assistant_text = _extract_assistant_text(response_payload)
            response_record = {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "request_id": request_identifier,
                "runtime": runtime,
                "base_url": normalized_base_url,
                "status": ProbeStatus.OK.value,
                "component": "smoke_response",
                "timestamp_utc": utc_now_iso_z(),
                "monotonic_ns": monotonic_ns(),
                "response": response_payload,
                "extracted": {
                    "assistant_text": assistant_text,
                },
                "details": _smoke_record_details(
                    runtime=runtime,
                    base_url=normalized_base_url,
                    request_url=request_url,
                    request_summary=request_summary,
                    response_summary=_smoke_response_summary(response_payload),
                    extracted={"assistant_text": assistant_text},
                ),
            }
        except Exception as error:  # pragma: no cover - exercised in tests via fake transport
            status = _status_from_exception(error)
            response_record = {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "request_id": request_identifier,
                "runtime": runtime,
                "base_url": normalized_base_url,
                "status": status.value,
                "component": "smoke_response",
                "timestamp_utc": utc_now_iso_z(),
                "monotonic_ns": monotonic_ns(),
                "response": None,
                "extracted": {"assistant_text": None},
                "details": _smoke_record_details(
                    runtime=runtime,
                    base_url=normalized_base_url,
                    request_url=request_url,
                    request_summary=request_summary,
                    response_summary=_smoke_response_summary(None),
                    extracted={"assistant_text": None},
                    reason=str(error),
                ),
                "error_type": type(error).__name__,
                "error_message": str(error),
            }

        append_jsonl(Path(output_dir) / "smoke_response.jsonl", response_record)
        return response_record
