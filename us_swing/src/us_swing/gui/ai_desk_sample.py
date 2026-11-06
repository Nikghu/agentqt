"""
Module: MD-GUI-034.009.M08 — AI Desk sample data
Parent SRD: SRD-GUI-034.009

Fixed sample rows for the AI Desk section frames. Pure Python, no Qt. A desk.db reader
replaces this later without any GUI change.
"""
from __future__ import annotations

from dataclasses import dataclass

SEAT_CAPS = {"Experts": 3, "Champions": 5, "Juniors": 30}
MONTHLY_BUDGET = 10.0
EVENING_RUN_ET = "16:25"
DATA_FOLDER = "~/.usswing/desk/"
LLM_SOURCES = (
    "OpenRouter (main)",
    "Claude Code CLI (rare heavy jobs)",
    "HuggingFace (special models)",
    "TypeSafe Jev (typed decisions, shadow trial)",
)


@dataclass(frozen=True)
class OrgNode:
    """One employee in the org chart."""

    name: str
    role: str
    state: str
    level: str
    children: tuple[OrgNode, ...] = ()


@dataclass(frozen=True)
class Approval:
    """One item waiting for the Master."""

    kind: str
    title: str
    detail: str


@dataclass(frozen=True)
class Candidate:
    """One hiring proposal and the pipeline stage it sits in."""

    name: str
    stage: int
    note: str


@dataclass(frozen=True)
class TaskCard:
    """One task on the board."""

    title: str
    employee: str
    priority: str
    deadline: str
    column: str


HIRING_STAGES = (
    "Proposed", "Master approval 1", "Shadow trial (2 weeks)", "Master approval 2", "Hired",
)
TASK_COLUMNS = ("Queued", "Running", "Done", "Failed")



def _juniors(label: str, code: tuple[str, ...], ai: tuple[str, ...] = ()) -> OrgNode:
    kids = tuple(OrgNode(n, "Junior (code)", "sleeping", "Junior") for n in code) + tuple(
        OrgNode(n, "Junior (AI)", "sleeping", "Junior") for n in ai
    )
    return OrgNode(f"Juniors: {label}", f"{len(kids)} seats", "", "Group", kids)


_DATA_JR = _juniors("data", (
    "Quote fetcher", "Bar loader", "Split checker", "Calendar loader", "Gap finder",
    "Stale-data finder",
))
_TECH_JR = _juniors("technical", (
    "Breadth counter", "Sector ranker", "RSI scanner", "Volume scanner", "Trend scanner",
    "Level mapper", "Pattern matcher",
))
_INTEL_JR = _juniors("intel", (
    "Headline fetcher", "Filing fetcher", "Earnings lister",
), ("News reader", "Filing summariser"))

ORG_TREE = OrgNode("Master (you)", "Approves every trade", "working", "Master", (
    OrgNode("Lead 1", "AI Trade Manager", "working", "Manager", (
        OrgNode("Expert 1", "Expert: Macro & Regime", "sleeping", "Expert"),
        OrgNode("Expert 2", "Expert: Sector & Money Flow", "sleeping", "Expert"),
        OrgNode("Expert 3", "Expert: Technical Setup", "working", "Expert"),
        OrgNode("Expert 4", "Risk Manager (can veto)", "sleeping", "Risk"),
        OrgNode("Engineer 1", "System Engineer", "sleeping", "Engineer", (
            OrgNode("Champion 1", "Champion: data", "sleeping", "Champion", (_DATA_JR,)),
            OrgNode("Champion 2", "Champion: technical", "working", "Champion", (_TECH_JR,)),
            OrgNode("Champion 3", "Champion: intel and news", "sleeping", "Champion", (_INTEL_JR,)),
        )),
        OrgNode("Expert 6", "Report page writer", "sleeping", "Writer"),
    )),
    OrgNode("Secretary 1", "Secretary: tasks, workload, cost", "sleeping", "Secretary"),
))



def _count(node: OrgNode, level: str) -> int:
    return int(node.level == level) + sum(_count(k, level) for k in node.children)


def seats_used() -> dict[str, int]:
    """Return seats taken per class, counted from the org tree."""
    return {
        "Experts": _count(ORG_TREE, "Expert"),
        "Champions": _count(ORG_TREE, "Champion"),
        "Juniors": _count(ORG_TREE, "Junior"),
    }


EMPLOYEE_COLUMNS = (
    "Name", "Role", "Level", "Model", "State", "Tasks today", "Cost today",
)
EMPLOYEES = (
    ("Lead 1", "AI Trade Manager", "Manager", "openrouter/cheap-chat", "working", "6", "$0.21"),
    ("Secretary 1", "Secretary", "Secretary", "openrouter/cheap-chat", "sleeping", "2", "$0.04"),
    ("Expert 1", "Macro & Regime", "Expert", "openrouter/cheap-reason", "sleeping", "1", "$0.09"),
    ("Expert 2", "Sector & Money Flow", "Expert", "openrouter/cheap-reason", "sleeping", "1", "$0.07"),
    ("Expert 3", "Technical Setup", "Expert", "openrouter/cheap-reason", "working", "3", "$0.12"),
    ("Expert 4", "Risk Manager", "Risk", "openrouter/cheap-reason", "sleeping", "2", "$0.05"),
    ("Engineer 1", "System Engineer", "Engineer", "claude-code-cli", "sleeping", "0", "$0.00"),
    ("Champion 1", "Data champion", "Champion", "openrouter/cheap-chat", "sleeping", "1", "$0.02"),
    ("Champion 2", "Technical champion", "Champion", "openrouter/cheap-chat", "working", "2", "$0.03"),
    ("Champion 3", "Intel champion", "Champion", "openrouter/cheap-chat", "sleeping", "1", "$0.06"),
    ("Expert 6", "Report page writer", "Writer", "openrouter/cheap-chat", "sleeping", "1", "$0.02"),
)

SOUL_TEXT = """\
# Expert 3 soul
You are Expert 3, the Technical Setup expert of the desk.
You judge chart setups from the data the champions hand you.
You never place orders. You send a short case to Lead 1 and Expert 4.
Say plainly when a setup is weak. Keep every note under 120 words.
"""

JOB_YAML = """\
name: Expert 3
level: expert
model: openrouter/cheap-reason
wakes_on:
  - event: scanner.candidates_ready
  - timer: "16:25 America/New_York"
tools:
  - read_bars
  - read_indicators
max_cost_per_task_usd: 0.05
reports_to: Lead 1
"""

APPROVALS = (
    Approval("Trade", "Long NVDA, 40 shares", "Entry 118.40, stop 114.90, target 127.00"),
    Approval("Trade", "Short XLE, 60 shares", "Entry 91.20, stop 93.10, target 86.80"),
    Approval("Hiring", "Jev decision junior (shadow)", "Typed decisions, 2 week shadow trial"),
)

RUN_COLUMNS = ("Time ET", "Run", "Result", "Duration", "Cost")
RUNS = (
    ("08:30", "Morning brief", "Done", "1m 12s", "$0.03"),
    ("10:00", "Sector scan", "Done", "48s", "$0.02"),
    ("12:15", "News sweep", "Failed", "21s", "$0.00"),
    ("16:25", "Evening run", "Queued", "-", "-"),
)

CHAT = (
    ("Lead 1", "Good morning. Three setups look strong today; two need your approval."),
    ("Master", "Show me the risk on the NVDA idea."),
    ("Lead 1", "Expert 4 allows it at 40 shares. The stop risks 0.4% of the account."),
    ("Master", "Fine, I will check the card."),
)

CANDIDATES = (
    Candidate("Jev decision junior (shadow)", 2, "Typed decisions; runs beside Expert 3"),
    Candidate("Earnings calendar junior", 0, "Plain code; lists earnings dates"),
)

TASKS = (
    TaskCard("Scan for breakouts", "Champion 2", "P1", "16:00", "Queued"),
    TaskCard("Draft evening brief", "Lead 1", "P0", "16:40", "Queued"),
    TaskCard("Rank sectors", "Expert 2", "P1", "10:15", "Running"),
    TaskCard("Refresh daily bars", "Champion 1", "P2", "09:00", "Done"),
    TaskCard("Weekly process report", "Secretary 1", "P2", "Fri 17:00", "Done"),
    TaskCard("Read overnight news", "Champion 3", "P1", "08:00", "Failed"),
)

TRACE_COLUMNS = ("Time", "Employee", "Step", "Model", "Tokens", "Cost", "Result")
TRACE = (
    ("10:02:11", "Expert 3", "Judge NVDA setup", "cheap-reason", "2,140", "$0.012", "Ok"),
    ("10:01:40", "Champion 2", "List candidates", "code", "0", "$0.000", "Ok"),
    ("09:58:03", "Lead 1", "Answer Master", "cheap-chat", "860", "$0.004", "Ok"),
    ("08:31:20", "Champion 3", "Read headlines", "cheap-chat", "3,300", "$0.015", "Retry"),
)
TRACE_DETAIL = (
    "Input:\n  NVDA daily bars (120), RSI 61, volume 1.4x average\n\n"
    "Output:\n  Setup: breakout above 117.80. Case is strong. Risk: gap fill near 114."
)

SCHEDULE_COLUMNS = ("Time ET", "Time IST", "Trigger", "Wakes", "Priority")
SCHEDULE = (
    ("08:30", "18:00", "Timer", "Lead 1, Secretary 1", "P1"),
    ("09:35", "19:05", "Market open event", "Champion 2", "P0"),
    ("12:00", "21:30", "Timer", "Champion 3", "P2"),
    ("16:25", "02:55", "Evening run", "Lead 1, Expert 1, Expert 2, Expert 3, Expert 4", "P0"),
    ("Fri 17:00", "Sat 02:30", "Weekly timer", "Secretary 1", "P2"),
)

REPORTS = {
    "Lead 1 evening brief": (
        "Lead 1 evening brief\n\nMarket closed mixed. Breadth was narrow.\n"
        "Two trade ideas wait for your approval. No risk limit was hit."
    ),
    "Secretary 1 weekly process report": (
        "Secretary 1 weekly process report\n\n41 tasks done, 3 failed. Spend USD 1.82.\n"
        "Idea: cache the news sweep to cut repeated reads."
    ),
    "Expert 1 regime note": (
        "Expert 1 regime note\n\nRegime: risk-on, volatility falling.\n"
        "Watch the dollar and the 10 year yield for a change."
    ),
}

SPENT = 1.82
COST_EMPLOYEE_COLUMNS = ("Employee", "Tokens", "Cost")
COST_EMPLOYEE = (
    ("Lead 1", "41,200", "$0.62"),
    ("Expert 3", "30,500", "$0.41"),
    ("Champion 3", "52,800", "$0.35"),
    ("Others", "28,000", "$0.44"),
)
COST_MODEL_COLUMNS = ("Model", "Tokens", "Cost")
COST_MODEL = (
    ("openrouter/cheap-chat", "98,000", "$0.97"),
    ("openrouter/cheap-reason", "54,500", "$0.85"),
)
