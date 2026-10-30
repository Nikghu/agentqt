# Traceability Matrix — MCP Server Module (MCP)

**Document ID:** TRACE-MCP
**Version:** 1.1.0
**Project:** US Swing Trading System
**Last Updated:** 2026-10-30

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status |
|---|---|---|---|---|---|---|
| FO-MCP-001 | SRD-MCP-001.001–004 | DD-MCP-001.001.D01 | MD-MCP-001.001.M01 | T01–T05 | `mcp/server.py` | Draft |
| FO-MCP-002 | SRD-MCP-002.001–002 | — | MD-MCP-002.001.M01 | T01–T03 | `mcp/tools/data_tools.py` | Draft |
| FO-MCP-003 | SRD-MCP-003.001–002 | — | MD-MCP-003.001.M01 | T01–T03 | `mcp/tools/screener_tools.py` | Draft |
| FO-MCP-004 | SRD-MCP-004.001 | — | MD-MCP-004.001.M01 | T01–T02 | `mcp/tools/analysis_tools.py` | Draft |
| FO-MCP-005 | SRD-MCP-005.001–003 | DD-MCP-005.001.D01 | MD-MCP-005.001.M01 | T01–T05 | `mcp/tools/execution_tools.py` | Draft |
| FO-MCP-006 | SRD-MCP-006.001 | — | MD-MCP-006.001.M01 | T01–T02 | `mcp/tools/health_tools.py` | Draft |
| FO-MCP-007 | SRD-MCP-007.001–.010 | None (minimal docs) | MD-MCP-007.001.M01, MD-MCP-007.004.M02 | UT-MCP-007.*: 8 tests (Pass) | `mcp/backtest_tools.py`, `mcp/jobs.py`, `mcp/__main__.py` | Implemented · RN-MCP-1.1.0-20261030 |

---

## Reverse Traceability

| Module | MD ID | Parent SRD | Parent FO |
|---|---|---|---|
| `mcp/server.py` | MD-MCP-001.001.M01 | SRD-MCP-001.001–004 | FO-MCP-001 |
| `mcp/tools/data_tools.py` | MD-MCP-002.001.M01 | SRD-MCP-002.001–002 | FO-MCP-002 |
| `mcp/tools/screener_tools.py` | MD-MCP-003.001.M01 | SRD-MCP-003.001–002 | FO-MCP-003 |
| `mcp/tools/analysis_tools.py` | MD-MCP-004.001.M01 | SRD-MCP-004.001 | FO-MCP-004 |
| `mcp/tools/execution_tools.py` | MD-MCP-005.001.M01 | SRD-MCP-005.001–003 | FO-MCP-005 |
| `mcp/tools/health_tools.py` | MD-MCP-006.001.M01 | SRD-MCP-006.001 | FO-MCP-006 |
| `mcp/backtest_tools.py` | MD-MCP-007.001.M01 | SRD-MCP-007.001 | FO-MCP-007 |
| `mcp/jobs.py` | MD-MCP-007.004.M02 | SRD-MCP-007.004 | FO-MCP-007 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 6 | 6 | 0 | 0 | 0 |
| SRD | 14 | 14 | 0 | 0 | 0 |
| DD | 2 | 2 | 0 | 0 | 0 |
| MD | 6 | 6 | 0 | 0 | 0 |
| UTCD | 20 | 20 | 0 | 0 | 0 |
| Code | 6 files | — | — | 0 | 0 |
