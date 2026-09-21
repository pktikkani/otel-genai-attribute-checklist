from parse import (
    attribute_rows,
    parse_deprecated_registry,
    parse_markdown_tables,
    parse_registry,
    split_markdown_row,
)


FIXTURE = """# Example

## Operation

| Key | Stability | Requirement Level | Value Type | Description | Example Values |
| --- | --- | --- | --- | --- | --- |
| [`gen_ai.request.model`](/registry) | ![Development](badge) | `Required` | string | Model name. [1] | `gpt-4` |
| [`gen_ai.request.stream`](/registry) | ![Development](badge) | `Conditionally Required` When streaming. | boolean | Streaming mode. | `true` |
"""


def test_split_markdown_row_preserves_inline_code_pipe() -> None:
    assert split_markdown_row(r"| `a|b` | c \| d |") == ["`a|b`", r"c \| d"]


def test_parse_small_attribute_fixture() -> None:
    tables = parse_markdown_tables(FIXTURE, "fixture.md")
    assert len(tables) == 1
    rows = attribute_rows(tables[0])
    assert [row.name for row in rows] == ["gen_ai.request.model", "gen_ai.request.stream"]
    assert rows[0].stability == "Development"
    assert rows[1].requirement == "Conditionally Required When streaming."
    assert rows[1].value_type == "boolean"


def test_registry_fixture_is_sorted() -> None:
    registry_md = """# Registry
| Key | Stability | Value Type | Description | Example Values |
| --- | --- | --- | --- | --- |
| <a>`gen_ai.z`</a> | ![Development](badge) | string | Zed. | `z` |
| <a>`gen_ai.a`</a> | ![Development](badge) | int | A. | `1` |
"""
    assert [row.name for row in parse_registry(registry_md)] == ["gen_ai.a", "gen_ai.z"]


def test_deprecated_parser_ignores_moved_section() -> None:
    registry_md = """# Registry
## GenAI Attributes (Moved)
| Key | Stability | Value Type | Description | Example Values |
| --- | --- | --- | --- | --- |
| `gen_ai.current` | Deprecated Moved to the new repository. | string | Current. | `x` |
## Deprecated GenAI Attributes
| Key | Stability | Value Type | Description | Example Values |
| --- | --- | --- | --- | --- |
| `gen_ai.old` | Deprecated Removed, no replacement at this time. | string | Deprecated, use Event API. | `x` |
## Deprecated OpenAI GenAI Attributes
| Key | Stability | Value Type | Description | Example Values |
| --- | --- | --- | --- | --- |
| `gen_ai.openai.old` | Deprecated Replaced by `openai.new`. | int | Deprecated, use `openai.new`. | `1` |
"""
    rows = parse_deprecated_registry(registry_md)
    assert [row.name for row in rows] == ["gen_ai.old", "gen_ai.openai.old"]
    assert rows[0].value_type == "string"
    assert rows[0].deprecation_note == "Removed, no replacement at this time."
    assert rows[1].replacement_text == "Deprecated, use openai.new."
