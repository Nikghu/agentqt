# Revision Note — RN-DSK-0.13.0-20261113

**Version:** 0.13.0
**Date:** 2026-11-13
**Tool:** DSK
**Artifact:** FO-DSK-011, FO-DSK-012 / SRD-DSK-011.001–.014, SRD-DSK-012.001–.011 (plus changed MD-DSK-001.010.M04)
**Type:** Feature

---

## Summary

AI Desk v3 phase M0: the message format and the tool registry are in place. Messages use one `desk.msg/1` envelope with nine body types, and the tools and table formats the desk can call are kept in `desk.db` in the MCP tool shape. The registry fills on desk start, so no behaviour changes yet. Nothing sends messages yet; that starts in M1.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-011.001.M27 | `src/us_swing/core/desk_msg.py` | New: `desk.msg/1` Pydantic models (thread, envelope, 9 body types by discriminator, want, verdict, data block, meta), 8 A2A states, dump/load/reason/parse_body, JSON Schema export |
| MD-DSK-012.001.M28 | `src/us_swing/core/desk_registry.py` | New: `desk.tool/1` and `desk.schema/1` models, `tools` and `schemas` tables, seed (22 tools, 5 formats), fill on start, read functions |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Changed: `start()` calls `fill_registry` inside try/except |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-011.001 | Every message is one `desk.msg/1` envelope: core header, body and optional meta, in one thread | Implemented |
| SRD-DSK-011.002 | A thread holds id, starter, message count, send-back rounds, state, opened and closed | Implemented |
| SRD-DSK-011.003 | The core header holds id, thread, parent, type, sender, to and at, plus due and state | Implemented |
| SRD-DSK-011.004 | An address is an employee id, `skill:<key>`, `champion:<key>`, `boss` or `master` | Implemented |
| SRD-DSK-011.005 | The type is one of nine values and picks the body model; bodies refuse unknown keys | Implemented |
| SRD-DSK-011.006 | Each type's body has its required and optional fields; a missing required field is refused | Implemented |
| SRD-DSK-011.007 | Body fields keep their size limits | Implemented |
| SRD-DSK-011.008 | A want holds goal, done test, inputs and optional schema, columns, tools and token cap | Implemented |
| SRD-DSK-011.009 | A verdict result is allowed only for its type | Implemented |
| SRD-DSK-011.010 | A data block names a schema-library format and holds rows (at most 200) or a reference with a row count | Implemented |
| SRD-DSK-011.011 | Meta holds only ai, used, secs, blocked and schema, each written only when it has a value | Implemented |
| SRD-DSK-011.012 | Message states are submitted, working, input_required, completed, failed, canceled, refused and expired | Implemented |
| SRD-DSK-011.013 | The envelope and each body type export as JSON Schema | Implemented |
| SRD-DSK-011.014 | M0 adds the format only; no desk step, skill or table sends or stores messages | Implemented |
| SRD-DSK-012.001 | Each tool is a `desk.tool/1` row with name, kind, version, description, schemas, ai and status | Implemented |
| SRD-DSK-012.002 | Own tool names are `group.tool`; MCP names are `mcp:server/tool`; a version adds `@<version>` | Implemented |
| SRD-DSK-012.003 | Each table format is a `desk.schema/1` row with id `<name>.v<N>`, title and columns | Implemented |
| SRD-DSK-012.004 | Tools and formats are kept in `tools` and `schemas` tables in `desk.db` | Implemented |
| SRD-DSK-012.005 | Each desk step is a code tool `step.<key>` | Implemented |
| SRD-DSK-012.006 | Each research skill is an AI tool `research.<kind>` | Implemented |
| SRD-DSK-012.007 | The data recipe is a code tool `data.recipe`; each recipe source is a format `<source>.v1` | Implemented |
| SRD-DSK-012.008 | Each Backtest MCP tool is an MCP tool `mcp:backtest/<tool>` | Implemented |
| SRD-DSK-012.009 | On each desk start the registry is filled from the lists without copies; a seeded tool no longer in code is set off, never deleted | Implemented |
| SRD-DSK-012.010 | Read functions list tools and formats and get one by name; read-only | Implemented |
| SRD-DSK-012.011 | Filling the registry is logged with the tool and format counts (`[Tools]` prefix) | Implemented |

---

## Design Decisions

- One envelope `desk.msg/1` for all messages; the body shape depends on the type.
- Tool registry uses the MCP tool shape (`desk.tool/1`) so later MCP work needs no new format.
- Tools that are no longer in code are set off, not deleted, so history stays readable.
- Seeded set: 8 `step.*` tools, 5 `research.*` tools, `data.recipe`, 8 `mcp:backtest/*` tools (22 tools) and 5 `<source>.v1` formats.
- Left out of M0 by user decision: priority from type (moved to M1), tool result shape, tool owner and limits, and "tools that make a format" (moved to M6).

---

## Issues Resolved

None

---

## Test Coverage

52 new UTCD cases, all Pass: UT-DSK-011.* (28, `tests/desk/test_desk_msg.py`), UT-DSK-012.* (22, `tests/desk/test_desk_registry.py`), plus UT-DSK-001.010.M04.T32–T33 (2, Pass) for the start hook. Coverage 99% (msg) and 98% (registry). Desk and market suites: 947 passed. ruff and mypy --strict clean. Code review approved; 5 small fixes applied (MCP seed failure isolated, description capped at 300 characters, off-marking edits JSON, meeting needs at least one recipient, read errors logged).

Open: FO-DSK-011 and FO-DSK-012 still Draft in the FO files; user to approve. Branch `feat/dsk-m0-schema-registry`, not pushed.
