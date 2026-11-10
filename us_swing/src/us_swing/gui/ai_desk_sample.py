"""
Module: MD-GUI-034.009.M08 — AI Desk sample data
Parent SRD: SRD-GUI-034.009

Fixed sample rows for the AI Desk section frames. Pure Python, no Qt. A desk.db reader
replaces this later without any GUI change.
"""
from __future__ import annotations

SEAT_CAPS = {"Experts": 3, "Champions": 5, "Juniors": 30}
MONTHLY_BUDGET = 10.0
DATA_FOLDER = "~/.usswing/desk/"
LLM_SOURCES = (
    "OpenRouter (main)",
    "Claude Code CLI (rare heavy jobs)",
    "HuggingFace (special models)",
    "TypeSafe Jev (typed decisions, shadow trial)",
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
