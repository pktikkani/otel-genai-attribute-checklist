#!/usr/bin/env python3
"""Download the exact source files used by the checklist build."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

REPO = "open-telemetry/semantic-conventions-genai"
SHA = "c88d504ab3d9879f8e50d3cc87e69775e11db234"
RAW_ROOT = f"https://raw.githubusercontent.com/{REPO}/{SHA}"
LEGACY_REPO = "open-telemetry/semantic-conventions"
LEGACY_SHA = "d0472f4ae331e8ef01aa571fe024d0d6a1a9b5e1"
LEGACY_RAW_ROOT = f"https://raw.githubusercontent.com/{LEGACY_REPO}/{LEGACY_SHA}"
HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE / "source" / SHA
LEGACY_SOURCE_ROOT = HERE / "source" / LEGACY_SHA

FILES = (
    "LICENSE",
    "docs/registry/attributes/gen-ai.md",
    "docs/registry/attributes/mcp.md",
    "docs/registry/attributes/openai.md",
    "docs/registry/attributes/aws.md",
    "docs/gen-ai/README.md",
    "docs/gen-ai/gen-ai-spans.md",
    "docs/gen-ai/gen-ai-agent-spans.md",
    "docs/gen-ai/gen-ai-events.md",
    "docs/gen-ai/gen-ai-exceptions.md",
    "docs/gen-ai/gen-ai-metrics.md",
    "docs/gen-ai/mcp.md",
    "docs/gen-ai/openai.md",
    "docs/gen-ai/anthropic.md",
    "docs/gen-ai/aws-bedrock.md",
    "docs/gen-ai/azure-ai-inference.md",
    "docs/gen-ai/non-normative/examples-llm-calls.md",
)

LEGACY_FILES = ("docs/registry/attributes/gen-ai.md",)


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "otel-checklist-builder/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_repository(
    repository: str,
    commit: str,
    raw_root: str,
    source_root: Path,
    files: tuple[str, ...],
) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for relative in files:
        payload = download(f"{raw_root}/{relative}")
        target = source_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        checksums[relative] = hashlib.sha256(payload).hexdigest()
    manifest = {
        "repository": f"https://github.com/{repository}",
        "commit": commit,
        "raw_root": raw_root,
        "files": checksums,
    }
    (source_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return checksums


def fetch_all() -> dict[str, dict[str, str]]:
    return {
        REPO: fetch_repository(REPO, SHA, RAW_ROOT, SOURCE_ROOT, FILES),
        LEGACY_REPO: fetch_repository(
            LEGACY_REPO,
            LEGACY_SHA,
            LEGACY_RAW_ROOT,
            LEGACY_SOURCE_ROOT,
            LEGACY_FILES,
        ),
    }


if __name__ == "__main__":
    fetched = fetch_all()
    count = sum(len(files) for files in fetched.values())
    print(f"Fetched {count} pinned files across {len(fetched)} repositories")
