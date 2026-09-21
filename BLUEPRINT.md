# Blueprint

> Every session: reread this file before writing code. New features conform to this structure, or you update this file FIRST with a dated decision note (`## YYYY-MM-DD — <what changed and why>`).

## Stack
Python 3.12+ with uv, Jinja templates, WeasyPrint, pytest, and pinned Markdown snapshots. Keep the current flat scripts; reconsider packaging only if a reusable API emerges.

## Structure and boundaries
- `fetch.py`: download and checksum pinned upstream files into `source/`.
- `parse.py`: pure Markdown-to-typed-row parsing.
- `build.py`, `template.html`, `partials/`, `style.css`: assemble and render both editions.
- `tests/`: parser and source/checklist invariants.
- `dist/`: committed public PDFs; `docs/`: committed README imagery.

Pinned SHAs live only in `fetch.py`; manifests and PDFs derive from them. Attribute definitions live only in `source/`; rendered text derives from snapshots.

Likely changes stay isolated: upstream pin (`fetch.py`), parsing rule (`parse.py`), layout (`template.html`/CSS), checklist selection (`build.py`), or verification (`tests/`).

## Limits
Code: 400 lines/file and 50 lines/function where practical; existing extraction code is grandfathered. Log decision points and error boundaries; never log secrets.

## Roadmap
- No planned features; keep the pinned PDFs reproducible and the README commands truthful.
