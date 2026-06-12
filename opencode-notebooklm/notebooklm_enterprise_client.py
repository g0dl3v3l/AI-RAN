#!/usr/bin/env python3
"""Minimal NotebookLM Enterprise API client for OpenCode workflows.

This wrapper uses official NotebookLM Enterprise v1alpha REST endpoints hosted on
Discovery Engine. It focuses on notebook/source lifecycle operations that are
currently documented:

- notebooks.create
- notebooks.get
- notebooks.listRecentlyViewed
- notebooks.batchDelete
- notebooks.share
- notebooks.sources.batchCreate
- notebooks.sources.uploadFile
- notebooks.sources.get
- notebooks.sources.batchDelete

Environment variables:
- NOTEBOOKLM_PROJECT_NUMBER (required)
- NOTEBOOKLM_LOCATION (required, e.g. us/eu/global)
- NOTEBOOKLM_ENDPOINT_LOCATION (optional; defaults to NOTEBOOKLM_LOCATION)
- NOTEBOOKLM_BEARER_TOKEN (optional; if absent, uses `gcloud auth print-access-token`)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class NotebookLMEnterpriseClient:
    """Thin REST client for NotebookLM Enterprise APIs."""

    def __init__(
        self,
        *,
        project_number: str,
        location: str,
        endpoint_location: str,
        bearer_token: str,
    ) -> None:
        self.project_number = project_number
        self.location = location
        self.endpoint_location = endpoint_location
        self.base_url = (
            "https://"
            f"{self.endpoint_location}-discoveryengine.googleapis.com/v1alpha/"
            f"projects/{self.project_number}/locations/{self.location}"
        )
        self._auth_header = f"Bearer {bearer_token}"

    def _request(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
        content_type: str = "application/json",
        raw_body: bytes | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query)}"

        if raw_body is not None:
            payload = raw_body
        elif body is None:
            payload = None
        else:
            payload = json.dumps(body).encode("utf-8")

        request = Request(url=url, data=payload, method=method)
        request.add_header("Authorization", self._auth_header)
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", content_type)

        try:
            with urlopen(request) as response:
                response_payload = response.read().decode("utf-8")
                if not response_payload:
                    return {}
                return json.loads(response_payload)
        except HTTPError as error:
            response_payload = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {error.code} calling {method} {url}: {response_payload}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"Network error calling {method} {url}: {error}") from error

    # --- Notebook methods ---

    def create_notebook(self, title: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="notebooks",
            body={"title": title},
        )

    def get_notebook(self, notebook_id: str) -> dict[str, Any]:
        return self._request(method="GET", path=f"notebooks/{notebook_id}")

    def list_recently_viewed(self, page_size: int = 25) -> dict[str, Any]:
        return self._request(
            method="GET",
            path="notebooks:listRecentlyViewed",
            query={"pageSize": str(page_size)},
        )

    def batch_delete_notebooks(self, notebook_ids: list[str]) -> dict[str, Any]:
        names = [
            f"projects/{self.project_number}/locations/{self.location}/notebooks/{notebook_id}"
            for notebook_id in notebook_ids
        ]
        return self._request(
            method="POST",
            path="notebooks:batchDelete",
            body={"names": names},
        )

    def share_notebook(
        self,
        notebook_id: str,
        *,
        emails: list[str],
        role: str = "PROJECT_ROLE_READER",
        notify_via_email: bool = True,
    ) -> dict[str, Any]:
        # Official request body: accountAndRoles[] + notifyViaEmail (required).
        account_and_roles = [{"email": email, "role": role} for email in emails]
        return self._request(
            method="POST",
            path=f"notebooks/{notebook_id}:share",
            body={
                "accountAndRoles": account_and_roles,
                "notifyViaEmail": notify_via_email,
            },
        )

    # --- Source methods ---

    def batch_create_sources(
        self,
        notebook_id: str,
        sources_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=f"notebooks/{notebook_id}/sources:batchCreate",
            body=sources_payload,
        )

    def upload_file_source(
        self,
        notebook_id: str,
        file_path: Path,
        *,
        mime_type: str,
    ) -> dict[str, Any]:
        # Official upload endpoint uses /upload/v1alpha and requires X-Goog-Upload-* headers.
        url = (
            "https://"
            f"{self.endpoint_location}-discoveryengine.googleapis.com/upload/v1alpha/"
            f"projects/{self.project_number}/locations/{self.location}/"
            f"notebooks/{notebook_id}/sources:uploadFile"
        )
        request = Request(url=url, data=file_path.read_bytes(), method="POST")
        request.add_header("Authorization", self._auth_header)
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", mime_type)
        request.add_header("X-Goog-Upload-File-Name", file_path.name)
        request.add_header("X-Goog-Upload-Protocol", "raw")

        try:
            with urlopen(request) as response:
                response_payload = response.read().decode("utf-8")
                if not response_payload:
                    return {}
                return json.loads(response_payload)
        except HTTPError as error:
            response_payload = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {error.code} calling POST {url}: {response_payload}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"Network error calling POST {url}: {error}") from error

    def get_source(self, notebook_id: str, source_id: str) -> dict[str, Any]:
        return self._request(
            method="GET",
            path=f"notebooks/{notebook_id}/sources/{source_id}",
        )

    def batch_delete_sources(
        self,
        notebook_id: str,
        source_ids: list[str],
    ) -> dict[str, Any]:
        names = [
            "projects/"
            f"{self.project_number}/locations/{self.location}/"
            f"notebooks/{notebook_id}/sources/{source_id}"
            for source_id in source_ids
        ]
        return self._request(
            method="POST",
            path=f"notebooks/{notebook_id}/sources:batchDelete",
            body={"names": names},
        )


def _resolve_bearer_token() -> str:
    env_token = os.getenv("NOTEBOOKLM_BEARER_TOKEN")
    if env_token:
        return env_token

    command = ["gcloud", "auth", "print-access-token"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise RuntimeError(
            "Unable to resolve bearer token. Set NOTEBOOKLM_BEARER_TOKEN or install "
            "gcloud and login via `gcloud auth login` (and optionally "
            "`gcloud auth login --enable-gdrive-access` for Drive-backed sources)."
        ) from error

    token = result.stdout.strip()
    if not token:
        raise RuntimeError("gcloud returned an empty access token.")
    return token


def _build_client() -> NotebookLMEnterpriseClient:
    project_number = os.getenv("NOTEBOOKLM_PROJECT_NUMBER")
    location = os.getenv("NOTEBOOKLM_LOCATION")
    endpoint_location = os.getenv("NOTEBOOKLM_ENDPOINT_LOCATION") or location

    if not project_number or not location or not endpoint_location:
        raise RuntimeError(
            "Missing env vars. Required: NOTEBOOKLM_PROJECT_NUMBER, NOTEBOOKLM_LOCATION. "
            "Optional: NOTEBOOKLM_ENDPOINT_LOCATION."
        )

    token = _resolve_bearer_token()
    return NotebookLMEnterpriseClient(
        project_number=project_number,
        location=location,
        endpoint_location=endpoint_location,
        bearer_token=token,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NotebookLM Enterprise lifecycle helper (official API only)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_list = subparsers.add_parser("list-recent", help="List recently viewed notebooks")
    parser_list.add_argument("--page-size", type=int, default=25)

    parser_create = subparsers.add_parser("create", help="Create a notebook")
    parser_create.add_argument("--title", required=True)

    parser_get = subparsers.add_parser("get", help="Get notebook details")
    parser_get.add_argument("--notebook-id", required=True)

    parser_share = subparsers.add_parser("share", help="Share a notebook")
    parser_share.add_argument("--notebook-id", required=True)
    parser_share.add_argument("--emails", required=True, help="Comma-separated email list")
    parser_share.add_argument("--role", default="PROJECT_ROLE_READER")

    parser_delete = subparsers.add_parser("delete", help="Batch delete notebooks")
    parser_delete.add_argument(
        "--notebook-ids",
        required=True,
        help="Comma-separated notebook IDs",
    )

    parser_source_upload = subparsers.add_parser(
        "source-upload", help="Upload file as source"
    )
    parser_source_upload.add_argument("--notebook-id", required=True)
    parser_source_upload.add_argument("--file", required=True)
    parser_source_upload.add_argument(
        "--mime-type", default="application/pdf", help="Content type for upload"
    )

    parser_source_batch_create = subparsers.add_parser(
        "source-batch-create",
        help="Create non-file sources from JSON payload",
    )
    parser_source_batch_create.add_argument("--notebook-id", required=True)
    parser_source_batch_create.add_argument(
        "--payload-json",
        required=True,
        help="Path to JSON file that matches batchCreate request body",
    )

    parser_source_get = subparsers.add_parser("source-get", help="Get source details")
    parser_source_get.add_argument("--notebook-id", required=True)
    parser_source_get.add_argument("--source-id", required=True)

    parser_source_delete = subparsers.add_parser(
        "source-delete", help="Batch delete sources"
    )
    parser_source_delete.add_argument("--notebook-id", required=True)
    parser_source_delete.add_argument(
        "--source-ids",
        required=True,
        help="Comma-separated source IDs",
    )

    return parser.parse_args()


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    args = _parse_args()
    client = _build_client()

    try:
        if args.command == "list-recent":
            _print_json(client.list_recently_viewed(page_size=args.page_size))
        elif args.command == "create":
            _print_json(client.create_notebook(title=args.title))
        elif args.command == "get":
            _print_json(client.get_notebook(notebook_id=args.notebook_id))
        elif args.command == "share":
            emails = [email.strip() for email in args.emails.split(",") if email.strip()]
            _print_json(
                client.share_notebook(
                    notebook_id=args.notebook_id,
                    emails=emails,
                    role=args.role,
                )
            )
        elif args.command == "delete":
            notebook_ids = [
                notebook_id.strip()
                for notebook_id in args.notebook_ids.split(",")
                if notebook_id.strip()
            ]
            _print_json(client.batch_delete_notebooks(notebook_ids=notebook_ids))
        elif args.command == "source-upload":
            _print_json(
                client.upload_file_source(
                    notebook_id=args.notebook_id,
                    file_path=Path(args.file),
                    mime_type=args.mime_type,
                )
            )
        elif args.command == "source-batch-create":
            payload_path = Path(args.payload_json)
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            _print_json(
                client.batch_create_sources(
                    notebook_id=args.notebook_id,
                    sources_payload=payload,
                )
            )
        elif args.command == "source-get":
            _print_json(
                client.get_source(
                    notebook_id=args.notebook_id,
                    source_id=args.source_id,
                )
            )
        elif args.command == "source-delete":
            source_ids = [
                source_id.strip()
                for source_id in args.source_ids.split(",")
                if source_id.strip()
            ]
            _print_json(
                client.batch_delete_sources(
                    notebook_id=args.notebook_id,
                    source_ids=source_ids,
                )
            )
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")

        return 0
    except Exception as error:  # pragma: no cover - CLI fallback
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
