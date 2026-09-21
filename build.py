#!/usr/bin/env python3
"""Compile pinned OpenTelemetry Markdown rows into HTML and a paged PDF."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fetch import (
    LEGACY_REPO,
    LEGACY_SHA,
    LEGACY_SOURCE_ROOT,
    REPO,
    SHA,
    SOURCE_ROOT,
)
from parse import (
    AttributeRow,
    extract_bold_statement,
    extract_section,
    parse_markdown_tables,
    parse_deprecated_registry,
    parse_metrics,
    parse_registry,
    tables_by_section,
    attribute_rows,
)

HERE = Path(__file__).resolve().parent
BUILD_DIR = HERE / "build"
DIST_DIR = Path("dist")
DEFAULT_OUTPUT = DIST_DIR / "OpenTelemetry GenAI Attribute Checklist.pdf"
SHORT_OUTPUT = DIST_DIR / "OpenTelemetry GenAI Attribute Checklist - Short.pdf"
COMPILED_DATE = "2026-09-21"
REPO_URL = f"https://github.com/{REPO}"
LEGACY_REPO_URL = f"https://github.com/{LEGACY_REPO}"


def ensure_macos_native_library_path() -> None:
    """Re-exec once so uv's Python can resolve existing Homebrew Pango/GLib."""
    homebrew_lib = "/opt/homebrew/lib"
    current = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if sys.platform == "darwin" and Path(homebrew_lib).is_dir() and homebrew_lib not in current.split(":"):
        environment = dict(os.environ)
        environment["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(filter(None, (homebrew_lib, current)))
        os.execvpe(sys.executable, [sys.executable, *sys.argv], environment)


def read_source(relative: str) -> str:
    return (SOURCE_ROOT / relative).read_text(encoding="utf-8")


def source_url(relative: str) -> str:
    return f"{REPO_URL}/blob/{SHA}/{relative}"


def legacy_source_url(relative: str) -> str:
    return f"{LEGACY_REPO_URL}/blob/{LEGACY_SHA}/{relative}"


def remove_footnotes(value: str) -> str:
    return re.sub(r"\s*\[\d+\]", "", value).strip()


def shorten(value: str, limit: int) -> str:
    """Shorten by taking an exact source prefix, never by paraphrasing."""
    text = remove_footnotes(value)
    if len(text) <= limit:
        return text
    prefix = text[: limit - 1].rstrip()
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return prefix.rstrip(" ,;:") + "…"


def requirement_parts(value: str) -> tuple[str, str, str]:
    cleaned = remove_footnotes(value)
    for label, kind in (
        ("Conditionally Required", "conditional"),
        ("Required", "required"),
        ("Recommended", "recommended"),
        ("Opt-In", "opt-in"),
    ):
        if cleaned.lower().startswith(label.lower()):
            detail = cleaned[len(label) :].strip(" .")
            return label, detail, kind
    return cleaned or "—", "", "other"


def anchor_for(name: str) -> str:
    return "attr-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def row_for_template(row: AttributeRow, registry_names: set[str]) -> dict[str, Any]:
    label, detail, kind = requirement_parts(row.requirement)
    return {
        **asdict(row),
        "description": shorten(row.description, 175),
        "example": shorten(row.example, 92) or "—",
        "requirement_label": label,
        "requirement_detail": detail,
        "requirement_kind": kind,
        "registry_anchor": anchor_for(row.name) if row.name in registry_names else "",
    }


def convention(markdown: str, heading: str) -> dict[str, str]:
    section = extract_section(markdown, heading)
    return {
        "span_name": extract_bold_statement(section, "Span name"),
        "span_kind": extract_bold_statement(section, "Span kind"),
    }


def checklist_table(
    title: str,
    source: str,
    rows: tuple[AttributeRow, ...],
    registry_names: set[str],
    conventions: dict[str, str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    return {
        "title": title,
        "source": source,
        "source_url": source_url(source),
        "rows": [row_for_template(row, registry_names) for row in rows],
        "conventions": conventions or {},
        "note": note,
    }


def _collect_full_document() -> dict[str, Any]:
    registry_source = "docs/registry/attributes/gen-ai.md"
    registry = parse_registry(read_source(registry_source), registry_source)
    registry_names = {row.name for row in registry}
    deprecated = parse_deprecated_registry(
        (LEGACY_SOURCE_ROOT / registry_source).read_text(encoding="utf-8"),
        registry_source,
    )

    spans_source = "docs/gen-ai/gen-ai-spans.md"
    spans_md = read_source(spans_source)
    spans = tables_by_section(spans_md, spans_source)

    agent_source = "docs/gen-ai/gen-ai-agent-spans.md"
    agent_md = read_source(agent_source)
    agents = tables_by_section(agent_md, agent_source)

    events_source = "docs/gen-ai/gen-ai-events.md"
    events_md = read_source(events_source)
    events = tables_by_section(events_md, events_source)

    sections = [
        {
            "id": "llm-inference",
            "title": "LLM inference span",
            "kicker": "Core client telemetry",
            "intro": "Apply the published inference span convention to model or service calls that generate a response or request a tool call.",
            "tables": [
                checklist_table(
                    "Inference",
                    spans_source,
                    spans["Inference"],
                    registry_names,
                    convention(spans_md, "Inference"),
                )
            ],
        },
        {
            "id": "embeddings",
            "title": "Embeddings span",
            "kicker": "Vector generation",
            "intro": "Use this convention for requests that generate embeddings from an input.",
            "tables": [
                checklist_table(
                    "Embeddings",
                    spans_source,
                    spans["Embeddings"],
                    registry_names,
                    convention(spans_md, "Embeddings"),
                )
            ],
        },
        {
            "id": "tool-execution",
            "title": "Tool-execution span",
            "kicker": "Agent tool calls",
            "intro": "Use this convention for tool execution, including tool calls made directly by application code.",
            "tables": [
                checklist_table(
                    "Execute tool",
                    spans_source,
                    spans["Execute tool span"],
                    registry_names,
                    convention(spans_md, "Execute tool span"),
                )
            ],
        },
        {
            "id": "agent-spans",
            "title": "Agent and workflow spans",
            "kicker": "Create, invoke, coordinate, plan",
            "intro": "Choose the operation that matches the agent or framework boundary being instrumented.",
            "tables": [
                checklist_table(title, agent_source, agents[title], registry_names, convention(agent_md, title))
                for title in (
                    "Create agent span",
                    "Invoke agent client span",
                    "Invoke agent internal span",
                    "Invoke workflow span",
                    "Plan span",
                )
            ],
        },
        {
            "id": "events",
            "title": "Events",
            "kicker": "Operation details and evaluation results",
            "intro": "Event names are fixed by the source headings; apply the attribute requirements for the selected event.",
            "tables": [
                checklist_table(title.removeprefix("Event: "), events_source, rows, registry_names)
                for title, rows in events.items()
            ],
        },
    ]

    metrics_source = "docs/gen-ai/gen-ai-metrics.md"
    metrics = []
    for metric in parse_metrics(read_source(metrics_source), metrics_source):
        metrics.append(
            {
                "name": metric.name,
                "instrument": metric.instrument,
                "unit": metric.unit,
                "description": shorten(metric.description, 155),
                "stability": metric.stability,
                "source": metric.source,
                "source_url": source_url(metric.source),
                "attributes": [row_for_template(row, registry_names) for row in metric.attributes],
            }
        )

    mcp_source = "docs/gen-ai/mcp.md"
    mcp_md = read_source(mcp_source)
    mcp_sections = tables_by_section(mcp_md, mcp_source)
    mcp_spans = [
        checklist_table(title, mcp_source, mcp_sections[title], registry_names, convention(mcp_md, title))
        for title in ("Client", "Server")
    ]
    mcp_metrics = []
    for metric in parse_metrics(mcp_md, mcp_source):
        mcp_metrics.append(
            {
                "name": metric.name,
                "instrument": metric.instrument,
                "unit": metric.unit,
                "description": shorten(metric.description, 155),
                "stability": metric.stability,
                "source": metric.source,
                "source_url": source_url(metric.source),
                "attributes": [row_for_template(row, registry_names) for row in metric.attributes],
            }
        )

    generic_sources = (
        spans_source,
        agent_source,
        events_source,
        metrics_source,
    )
    generic_names: set[str] = set()
    for source in generic_sources:
        for table in parse_markdown_tables(read_source(source), source):
            generic_names.update(row.name for row in attribute_rows(table))

    providers = []
    provider_specs = (
        ("OpenAI", "docs/gen-ai/openai.md", "Inference"),
        ("Anthropic", "docs/gen-ai/anthropic.md", "Inference"),
        ("AWS Bedrock", "docs/gen-ai/aws-bedrock.md", "AWS Bedrock Spans"),
        ("Azure AI Inference", "docs/gen-ai/azure-ai-inference.md", "Inference"),
    )
    for provider, source, main_heading in provider_specs:
        markdown = read_source(source)
        additions: list[AttributeRow] = []
        seen: set[str] = set()
        for table in parse_markdown_tables(markdown, source):
            for row in attribute_rows(table):
                if row.name not in generic_names and row.name not in seen:
                    additions.append(row)
                    seen.add(row.name)
        providers.append(
            {
                "name": provider,
                "source": source,
                "source_url": source_url(source),
                "conventions": convention(markdown, main_heading),
                "rows": [row_for_template(row, registry_names) for row in additions],
                "note": (
                    "No additional attribute key is unique to this provider page; apply its published mappings to the generic convention."
                    if not additions
                    else "Only keys present in this provider page and absent from the generic GenAI signal pages are listed."
                ),
            }
        )

    appendix = []
    for row in registry:
        appendix.append(
            {
                **asdict(row),
                "description": shorten(row.description, 205),
                "example": shorten(row.example, 92) or "—",
                "anchor": anchor_for(row.name),
                "source_url": source_url(registry_source),
            }
        )

    source_mapping = [
        ("LICENSE", "Cover: Apache License 2.0 source notice"),
        (registry_source, "Appendix A: complete gen_ai.* registry"),
        ("docs/registry/attributes/mcp.md", "MCP registry cross-check"),
        ("docs/registry/attributes/openai.md", "OpenAI additions cross-check"),
        ("docs/registry/attributes/aws.md", "AWS Bedrock additions cross-check"),
        (spans_source, "LLM inference, embeddings, tool execution"),
        (agent_source, "Agent and workflow spans"),
        (events_source, "Events"),
        (metrics_source, "Metrics"),
        (mcp_source, "MCP spans and metrics"),
        ("docs/gen-ai/openai.md", "OpenAI provider additions"),
        ("docs/gen-ai/anthropic.md", "Anthropic provider mapping"),
        ("docs/gen-ai/aws-bedrock.md", "AWS Bedrock provider additions"),
        ("docs/gen-ai/azure-ai-inference.md", "Azure AI Inference provider additions"),
        ("docs/gen-ai/README.md", "Repository section index; build evidence"),
        ("docs/gen-ai/gen-ai-exceptions.md", "Fetched reference; not separately tabulated"),
        ("docs/gen-ai/non-normative/examples-llm-calls.md", "Fetched reference; examples not copied into checklist rows"),
    ]

    deprecated_rows = [
        {
            **asdict(row),
            "source_url": legacy_source_url(row.source),
        }
        for row in deprecated
    ]

    return {
        "edition": "full",
        "title": "OpenTelemetry GenAI Attribute Checklist",
        "subtitle": "Compiled from the OpenTelemetry GenAI semantic conventions",
        "repo_url": REPO_URL,
        "sha": SHA,
        "short_sha": SHA[:12],
        "legacy_repo_url": LEGACY_REPO_URL,
        "legacy_sha": LEGACY_SHA,
        "legacy_short_sha": LEGACY_SHA[:12],
        "compiled_date": COMPILED_DATE,
        "deprecated": deprecated_rows,
        "sections": sections,
        "metrics": metrics,
        "mcp_spans": mcp_spans,
        "mcp_metrics": mcp_metrics,
        "providers": providers,
        "registry": appendix,
        "registry_count": len(appendix),
        "deprecated_count": len(deprecated_rows),
        "registry_deprecated_count": sum(1 for row in appendix if row["deprecated"]),
        "source_mapping": [
            {
                "repository": REPO,
                "path": path,
                "section": section,
                "url": source_url(path),
            }
            for path, section in source_mapping
        ]
        + [
            {
                "path": registry_source,
                "section": "Deprecated warning table; Moved section excluded",
                "url": legacy_source_url(registry_source),
                "repository": LEGACY_REPO,
            }
        ],
    }


def _included_short_row(row: dict[str, Any]) -> bool:
    return row["requirement_kind"] in {"required", "conditional", "recommended"}


def _short_table(table: dict[str, Any]) -> dict[str, Any]:
    selected = copy.deepcopy(table)
    selected["rows"] = [row for row in selected["rows"] if _included_short_row(row)]
    for row in selected["rows"]:
        row["description"] = shorten(row["description"], 78)
    return selected


def _table_by_title(data: dict[str, Any], section_id: str, table_title: str) -> dict[str, Any]:
    section = next(section for section in data["sections"] if section["id"] == section_id)
    return next(table for table in section["tables"] if table["title"] == table_title)


def _row_by_name(tables: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for table in tables:
        for row in table["rows"]:
            if row["name"] == name:
                return copy.deepcopy(row)
    raise KeyError(name)


def _collect_short_document(full: dict[str, Any]) -> dict[str, Any]:
    inference = _table_by_title(full, "llm-inference", "Inference")
    tool = _table_by_title(full, "tool-execution", "Execute tool")
    agent_tables = next(section for section in full["sections"] if section["id"] == "agent-spans")["tables"]
    selected_agents = [
        _short_table(next(table for table in agent_tables if table["title"] == title))
        for title in ("Create agent span", "Invoke agent client span")
    ]

    content_names = (
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
        "gen_ai.tool.definitions",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
    )
    content_tables = [inference, tool]
    content_rows = [_row_by_name(content_tables, name) for name in content_names]

    short_metrics = []
    for metric in full["metrics"]:
        if metric["name"] not in {
            "gen_ai.client.token.usage",
            "gen_ai.client.operation.duration",
        }:
            continue
        selected = copy.deepcopy(metric)
        selected["attributes"] = [
            row for row in selected["attributes"] if _included_short_row(row)
        ]
        short_metrics.append(selected)

    return {
        "edition": "short",
        "title": full["title"],
        "subtitle": "Short edition",
        "repo_url": full["repo_url"],
        "sha": full["sha"],
        "short_sha": full["short_sha"],
        "legacy_repo_url": full["legacy_repo_url"],
        "legacy_sha": full["legacy_sha"],
        "legacy_short_sha": full["legacy_short_sha"],
        "compiled_date": full["compiled_date"],
        "registry": full["registry"],
        "registry_count": full["registry_count"],
        "deprecated": copy.deepcopy(full["deprecated"]),
        "deprecated_count": full["deprecated_count"],
        "llm_table": _short_table(inference),
        "tool_table": _short_table(tool),
        "agent_tables": selected_agents,
        "content_rows": content_rows,
        "metrics": short_metrics,
        "content_source_url": source_url("docs/gen-ai/gen-ai-spans.md") + "#capturing-instructions-inputs-and-outputs",
    }


def collect_document(edition: str = "full") -> dict[str, Any]:
    if edition not in {"full", "short"}:
        raise ValueError(f"Unsupported edition: {edition}")
    full = _collect_full_document()
    return full if edition == "full" else _collect_short_document(full)


def pdf_page_count(path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(path)).pages)


def render(output: Path, edition: str = "full") -> tuple[Path, Path | None]:
    from weasyprint import CSS, HTML

    data = collect_document(edition)
    environment = Environment(
        loader=FileSystemLoader(HERE),
        autoescape=select_autoescape(("html", "xml")),
    )
    html_text = environment.get_template("template.html").render(**data)
    html_path: Path | None = None
    if edition == "full":
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        html_path = BUILD_DIR / "OpenTelemetry GenAI Attribute Checklist.html"
        data_path = BUILD_DIR / "pdf-data.json"
        html_path.write_text(html_text, encoding="utf-8")
        data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_text, base_url=str(HERE)).write_pdf(
        str(output),
        stylesheets=[CSS(filename=str(HERE / "style.css"))],
        presentational_hints=True,
    )
    if edition == "short":
        pages = pdf_page_count(output)
        assert 3 <= pages <= 5, f"Short edition must be 3-5 pages, got {pages}"
    return output, html_path


def main() -> None:
    ensure_macos_native_library_path()
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=("full", "short"), default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output_path = args.output or (DEFAULT_OUTPUT if args.edition == "full" else SHORT_OUTPUT)
    output, html_path = render(output_path, args.edition)
    if html_path is not None:
        print(f"HTML: {html_path}")
    print(f"PDF:  {output}")
    print(f"Pages: {pdf_page_count(output)}")


if __name__ == "__main__":
    main()
