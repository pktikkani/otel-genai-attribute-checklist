from build import collect_document
from fetch import LEGACY_SOURCE_ROOT, SOURCE_ROOT
from parse import parse_deprecated_registry, parse_registry


DEPRECATED_NAMES = {
    "gen_ai.completion",
    "gen_ai.prompt",
    "gen_ai.system",
    "gen_ai.usage.completion_tokens",
    "gen_ai.usage.prompt_tokens",
    "gen_ai.openai.request.response_format",
    "gen_ai.openai.request.seed",
    "gen_ai.openai.request.service_tier",
    "gen_ai.openai.response.service_tier",
    "gen_ai.openai.response.system_fingerprint",
}


def _all_pdf_attribute_names(data: dict) -> set[str]:
    names: set[str] = set()
    for section in data["sections"]:
        for table in section["tables"]:
            names.update(row["name"] for row in table["rows"])
    for metric in data["metrics"] + data["mcp_metrics"]:
        names.update(row["name"] for row in metric["attributes"])
    for table in data["mcp_spans"]:
        names.update(row["name"] for row in table["rows"])
    for provider in data["providers"]:
        names.update(row["name"] for row in provider["rows"])
    return names


def test_pinned_registry_has_72_unique_attributes() -> None:
    path = SOURCE_ROOT / "docs/registry/attributes/gen-ai.md"
    registry = parse_registry(path.read_text(encoding="utf-8"))
    assert len(registry) == 72
    assert len({row.name for row in registry}) == 72


def test_every_genai_attribute_in_pdf_data_exists_in_fetched_registry() -> None:
    data = collect_document()
    registry_names = {row["name"] for row in data["registry"]}
    pdf_genai_names = {name for name in _all_pdf_attribute_names(data) if name.startswith("gen_ai.")}
    assert pdf_genai_names <= registry_names


def test_pdf_appendix_exactly_matches_fetched_registry() -> None:
    data = collect_document()
    path = SOURCE_ROOT / "docs/registry/attributes/gen-ai.md"
    registry_names = {row.name for row in parse_registry(path.read_text(encoding="utf-8"))}
    assert {row["name"] for row in data["registry"]} == registry_names


def test_old_registry_parses_exactly_the_ten_truly_deprecated_names() -> None:
    path = LEGACY_SOURCE_ROOT / "docs/registry/attributes/gen-ai.md"
    rows = parse_deprecated_registry(path.read_text(encoding="utf-8"))
    assert {row.name for row in rows} == DEPRECATED_NAMES
    assert len(rows) == 10
    assert "gen_ai.request.model" not in {row.name for row in rows}


def test_truly_deprecated_names_never_appear_in_checklist_sections() -> None:
    assert DEPRECATED_NAMES.isdisjoint(_all_pdf_attribute_names(collect_document()))


def test_current_registry_has_no_deprecated_rows_and_old_count_is_separate() -> None:
    data = collect_document()
    assert data["registry_deprecated_count"] == 0
    assert data["deprecated_count"] == 10


def _short_checklist_rows(data: dict) -> list[dict]:
    rows = list(data["llm_table"]["rows"])
    rows.extend(data["tool_table"]["rows"])
    for table in data["agent_tables"]:
        rows.extend(table["rows"])
    for metric in data["metrics"]:
        rows.extend(metric["attributes"])
    return rows


def test_short_edition_has_no_opt_in_rows_outside_content_capture() -> None:
    data = collect_document("short")
    assert all(row["requirement_kind"] != "opt-in" for row in _short_checklist_rows(data))
    assert {row["requirement_kind"] for row in data["content_rows"]} == {"opt-in"}


def test_short_edition_content_capture_is_exactly_the_requested_six_rows() -> None:
    data = collect_document("short")
    assert [row["name"] for row in data["content_rows"]] == [
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
        "gen_ai.tool.definitions",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
    ]


def test_short_edition_has_only_the_two_requested_client_metrics() -> None:
    data = collect_document("short")
    assert [metric["name"] for metric in data["metrics"]] == [
        "gen_ai.client.token.usage",
        "gen_ai.client.operation.duration",
    ]


def test_short_edition_attributes_exist_in_fetched_registry() -> None:
    data = collect_document("short")
    registry_names = {row["name"] for row in data["registry"]}
    rows = _short_checklist_rows(data) + data["content_rows"]
    genai_names = {row["name"] for row in rows if row["name"].startswith("gen_ai.")}
    assert genai_names <= registry_names


def test_deprecated_names_never_appear_in_short_checklists() -> None:
    data = collect_document("short")
    names = {row["name"] for row in _short_checklist_rows(data) + data["content_rows"]}
    assert DEPRECATED_NAMES.isdisjoint(names)
