#!/usr/bin/env python3
"""Pure Markdown-table parsing helpers for pinned semantic-convention files."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class MarkdownTable:
    source: str
    headings: tuple[str, ...]
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def section(self) -> str:
        return self.headings[-1] if self.headings else ""


@dataclass(frozen=True)
class AttributeRow:
    source: str
    section: str
    name: str
    stability: str
    requirement: str
    value_type: str
    description: str
    example: str

    @property
    def requirement_kind(self) -> str:
        value = self.requirement.lower()
        if value.startswith("conditionally required"):
            return "conditional"
        if value.startswith("required"):
            return "required"
        if value.startswith("recommended"):
            return "recommended"
        if value.startswith("opt-in"):
            return "opt-in"
        return "other"


@dataclass(frozen=True)
class RegistryAttribute:
    name: str
    stability: str
    value_type: str
    description: str
    example: str
    deprecated: bool = False
    replacement: str = ""


@dataclass(frozen=True)
class DeprecatedAttribute:
    source: str
    section: str
    name: str
    value_type: str
    deprecation_note: str
    replacement_text: str


@dataclass(frozen=True)
class MetricDefinition:
    source: str
    section: str
    name: str
    instrument: str
    unit: str
    description: str
    stability: str
    attributes: tuple[AttributeRow, ...]


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")


def split_markdown_row(line: str) -> list[str]:
    """Split a pipe table row while respecting escaped pipes and inline code."""
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith(r"\|"):
        value = value[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    in_code = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif char == "`":
            in_code = not in_code
            current.append(char)
        elif char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def _is_separator(line: str, expected: int) -> bool:
    cells = split_markdown_row(line)
    return len(cells) == expected and all(SEPARATOR_RE.match(cell.strip()) for cell in cells)


def clean_inline(value: str) -> str:
    """Convert the small Markdown/HTML subset used in generated tables to text."""
    text = value.replace("\\|", "|")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_code_name(value: str) -> str:
    candidates = re.findall(r"`([^`]+)`", value)
    if candidates:
        return candidates[0].strip()
    return clean_inline(value)


def parse_markdown_tables(markdown: str, source: str = "") -> tuple[MarkdownTable, ...]:
    lines = markdown.splitlines()
    headings: list[str] = []
    tables: list[MarkdownTable] = []
    index = 0
    while index < len(lines):
        heading = HEADING_RE.match(lines[index])
        if heading:
            level = len(heading.group(1))
            headings[level - 1 :] = [clean_inline(heading.group(2))]
            index += 1
            continue
        if index + 1 < len(lines) and lines[index].lstrip().startswith("|"):
            header = split_markdown_row(lines[index])
            if header and _is_separator(lines[index + 1], len(header)):
                index += 2
                rows: list[tuple[str, ...]] = []
                while index < len(lines) and lines[index].lstrip().startswith("|"):
                    cells = split_markdown_row(lines[index])
                    if len(cells) < len(header):
                        cells.extend([""] * (len(header) - len(cells)))
                    rows.append(tuple(cells[: len(header)]))
                    index += 1
                tables.append(
                    MarkdownTable(
                        source=source,
                        headings=tuple(headings),
                        columns=tuple(clean_inline(cell) for cell in header),
                        rows=tuple(rows),
                    )
                )
                continue
        index += 1
    return tuple(tables)


def _column_index(columns: tuple[str, ...], *names: str) -> int | None:
    normalized = [column.lower() for column in columns]
    for name in names:
        if name.lower() in normalized:
            return normalized.index(name.lower())
    return None


def _cell(row: tuple[str, ...], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def attribute_rows(table: MarkdownTable) -> tuple[AttributeRow, ...]:
    key_index = _column_index(table.columns, "Key", "Attribute")
    if key_index is None or _column_index(table.columns, "Value Type") is None:
        return ()
    stability_index = _column_index(table.columns, "Stability")
    requirement_index = next(
        (i for i, column in enumerate(table.columns) if "requirement level" in column.lower()),
        None,
    )
    type_index = _column_index(table.columns, "Value Type")
    description_index = _column_index(table.columns, "Description")
    example_index = _column_index(table.columns, "Example Values", "Example Value", "Examples")
    result: list[AttributeRow] = []
    for raw in table.rows:
        result.append(
            AttributeRow(
                source=table.source,
                section=table.section,
                name=extract_code_name(_cell(raw, key_index)),
                stability=clean_inline(_cell(raw, stability_index)),
                requirement=clean_inline(_cell(raw, requirement_index)),
                value_type=clean_inline(_cell(raw, type_index)),
                description=clean_inline(_cell(raw, description_index)),
                example=clean_inline(_cell(raw, example_index)),
            )
        )
    return tuple(result)


def parse_registry(markdown: str, source: str = "docs/registry/attributes/gen-ai.md") -> tuple[RegistryAttribute, ...]:
    tables = parse_markdown_tables(markdown, source)
    registry_table = next(
        table for table in tables if tuple(column.lower() for column in table.columns[:3]) == ("key", "stability", "value type")
    )
    rows: list[RegistryAttribute] = []
    for attr in attribute_rows(registry_table):
        deprecated = "deprecated" in attr.stability.lower() or "deprecated" in attr.description.lower()
        replacement_match = re.search(r"(?:replaced by|use)\s+`?([a-z][a-z0-9_.-]+)`?", attr.description, re.IGNORECASE)
        rows.append(
            RegistryAttribute(
                name=attr.name,
                stability=attr.stability,
                value_type=attr.value_type,
                description=attr.description,
                example=attr.example,
                deprecated=deprecated,
                replacement=replacement_match.group(1) if replacement_match else "",
            )
        )
    return tuple(sorted(rows, key=lambda row: row.name))


def parse_deprecated_registry(
    markdown: str,
    source: str = "docs/registry/attributes/gen-ai.md",
) -> tuple[DeprecatedAttribute, ...]:
    """Parse only the two truly deprecated tables from the old registry.

    The adjacent ``GenAI Attributes (Moved)`` table deliberately does not
    participate: its red badges describe a repository move, not obsolete keys.
    """
    deprecated_sections = {
        "Deprecated GenAI Attributes",
        "Deprecated OpenAI GenAI Attributes",
    }
    rows: list[DeprecatedAttribute] = []
    for table in parse_markdown_tables(markdown, source):
        if table.section not in deprecated_sections:
            continue
        key_index = _column_index(table.columns, "Key")
        stability_index = _column_index(table.columns, "Stability")
        type_index = _column_index(table.columns, "Value Type")
        description_index = _column_index(table.columns, "Description")
        if key_index is None or type_index is None:
            continue
        for raw in table.rows:
            stability = clean_inline(_cell(raw, stability_index))
            note = re.sub(r"^Deprecated\s*", "", stability, count=1).strip()
            rows.append(
                DeprecatedAttribute(
                    source=source,
                    section=table.section,
                    name=extract_code_name(_cell(raw, key_index)),
                    value_type=clean_inline(_cell(raw, type_index)),
                    deprecation_note=note,
                    replacement_text=clean_inline(_cell(raw, description_index)),
                )
            )
    return tuple(rows)


def parse_metrics(markdown: str, source: str) -> tuple[MetricDefinition, ...]:
    tables = parse_markdown_tables(markdown, source)
    metrics: list[MetricDefinition] = []
    for index, table in enumerate(tables):
        if not table.columns or table.columns[0].lower() != "name":
            continue
        if "Instrument Type" not in table.columns or not table.rows:
            continue
        raw = table.rows[0]
        indexes = {column: i for i, column in enumerate(table.columns)}
        attrs: tuple[AttributeRow, ...] = ()
        if index + 1 < len(tables) and tables[index + 1].headings == table.headings:
            attrs = attribute_rows(tables[index + 1])
        metrics.append(
            MetricDefinition(
                source=source,
                section=table.section,
                name=extract_code_name(_cell(raw, indexes.get("Name"))),
                instrument=clean_inline(_cell(raw, indexes.get("Instrument Type"))),
                unit=clean_inline(_cell(raw, indexes.get("Unit (UCUM)"))),
                description=clean_inline(_cell(raw, indexes.get("Description"))),
                stability=clean_inline(_cell(raw, indexes.get("Stability"))),
                attributes=attrs,
            )
        )
    return tuple(metrics)


def tables_by_section(markdown: str, source: str) -> Mapping[str, tuple[AttributeRow, ...]]:
    grouped: dict[str, tuple[AttributeRow, ...]] = {}
    for table in parse_markdown_tables(markdown, source):
        rows = attribute_rows(table)
        if rows:
            grouped[table.section] = rows
    return grouped


def extract_section(markdown: str, heading: str) -> str:
    """Return the body of one exact heading, stopping at a peer or parent."""
    lines = markdown.splitlines()
    start = None
    level = None
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and clean_inline(match.group(2)) == heading:
            start = index + 1
            level = len(match.group(1))
            break
    if start is None or level is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        match = HEADING_RE.match(lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def extract_bold_statement(section: str, label: str) -> str:
    pattern = re.compile(rf"\*\*{re.escape(label)}\*\*:?\s*(.+(?:\n(?!\n|\*\*)[^\n]+)*)", re.IGNORECASE)
    match = pattern.search(section)
    return clean_inline(match.group(1)) if match else ""


def source_attribute_names(markdowns: Iterable[tuple[str, str]]) -> set[str]:
    names: set[str] = set()
    for source, markdown in markdowns:
        for table in parse_markdown_tables(markdown, source):
            names.update(row.name for row in attribute_rows(table))
    return names
