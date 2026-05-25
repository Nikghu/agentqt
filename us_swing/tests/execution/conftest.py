"""
Execution test package conftest.
Resolves the circular import between us_swing.broker and us_swing.data.
Loading data.models → broker.client → execution in the correct order
prevents the partially-initialized-module error that arises when
us_swing.execution.__init__ is the first module imported in the process.
"""
from __future__ import annotations

import us_swing.data.models  # noqa: F401 — must be first
import us_swing.broker.client  # noqa: F401 — resolves circular dep
