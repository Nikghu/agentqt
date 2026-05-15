Write pytest tests for a us_swing module from its UTCD document.

Usage: /project:write-tests <TOOL> <module_name>
Example: /project:write-tests INF broker/client.py — implement all UTCD tests for IBKRClient (connection, data fetch, timeout, reconnect), writing to us_swing/tests/infrastructure/test_client.py with UT-INF IDs in every docstring

**Agent:** Delegate to `.claude/agents/test-writer.md` (Sonnet) — it enforces UTCD traceability, UT ID docstrings, and fixture conventions automatically.

Steps:
0. Read `.claude/skills/dev-context.md` — process rules, artifact formats, doc rules
1. Read `us_swing/docs/<tool>/UTCD.md` — section for the specified module
2. Read the source file at `us_swing/src/usswing/<tool>/<module>.py`
3. Invoke `test-writer` agent to write all test cases to `us_swing/tests/<tool>/test_<module>.py`
4. Each test function docstring must reference its UT ID (e.g. `UT-INF-001.001.M01.T01: ...`)
5. Use fixtures from `conftest.py`; no global state
6. After writing, note which UTCD entries changed from `Not Run` → ready to run

$ARGUMENTS
