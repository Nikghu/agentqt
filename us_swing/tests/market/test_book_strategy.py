"""Tests for book to strategy research (FO-MKT-018, Autonomous desk step F skill 4)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx
from tests.market.test_lead_brief import _stage
from us_swing.core.desk_research import StepResult, Ticket
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.data.market_calendar import ET
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market.book_cards import CardText, already_read, books_block, save_card
from us_swing.market.book_strategy import BookStrategySkill, StrategyCard, found_quotes
from us_swing.market.book_text import (
    GUTENBERG_URL,
    BookError,
    BookRef,
    chapter,
    chapters,
    load_text,
    parse_topic,
    read_file,
)

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=ET)
PAD = " More words." * 60
BOOK = ("Contents\nCHAPTER I. Wait\nCHAPTER II. Breakouts\nCHAPTER III. Last\n\n"
        f"CHAPTER I\nThe first lesson is to wait.{PAD}\n\n"
        "CHAPTER II\nBuy when the price breaks above the old high on strong volume. "
        f"Sell half at twice the risk.{PAD}\n\nCHAPTER III\nThe last lesson.{PAD}\n")


def _ticket(topic: str = "upload:book.txt ch 2", state: dict[str, Any] | None = None,
            tid: int = 7) -> Ticket:
    return Ticket(
        id=tid, kind="book_to_strategy", topic=topic, goal="Turn the chapter into rules",
        done_test="A card with entry, exit and stop", token_cap=20_000, step_cap=8,
        time_cap_min=60, raised_by="l-1", raised_by_name="Lead A", status="running",
        made="2026-11-11T09:00:00-05:00", approved_by="master", approved=None, started=None,
        ended=None, tokens=0, steps=0, biggest=0, quiet_steps=0, last_call="",
        state=json.dumps(state or {}), result="", end_reason="", gain=None, updated=None)


def _no_web(url: str) -> str:
    raise AssertionError(f"no web call expected: {url}")


def _skill(get: Any = _no_web) -> BookStrategySkill:
    return BookStrategySkill(lambda: NOW, lambda home: home / "books", get)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "books").mkdir()
    (tmp_path / "books" / "book.txt").write_text(BOOK, encoding="utf-8")
    return tmp_path


def _card(stop: str = "Below the breakout day low", quotes: list[str] | None = None
          ) -> StrategyCard:
    return StrategyCard(name="Volume breakout", idea="Buy strength out of an old high",
                        market="Rising market", entry="Break above the old high on volume",
                        exit="Sell half at 2R", stop=stop,
                        quotes=quotes or ["Buy when the price breaks above the old high"])


def _run(home: Path, answer: StrategyCard | None) -> list[StepResult]:
    ctx = FakeCtx(home, None)
    skill = _skill()
    first = skill.step(ctx, _ticket())
    assert first is not None
    ctx.answer = answer
    second = skill.step(ctx, _ticket(state=first.state))
    assert second is not None
    return [first, second]


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# ---------------- steps ----------------

def test_two_steps(home: Path) -> None:
    """UT-MKT-018.001.M01.T01: Read and card end the ticket done."""
    steps = _run(home, _card())
    assert [s.call for s in steps] == ["read", "card"]
    assert [s.outcome for s in steps] == ["go", "done"]


def test_no_answer(home: Path) -> None:
    """UT-MKT-018.001.M01.T02: No card answer gives an empty note and outcome go."""
    steps = _run(home, None)
    assert steps[1].note == "" and steps[1].outcome == "go"


# ---------------- topic and sources ----------------

def test_topic_forms() -> None:
    """UT-MKT-018.002.M02.T01: Upload and Gutenberg topics are read."""
    assert parse_topic("upload:My Book.pdf ch 3") == BookRef("upload", "My Book.pdf", 3)
    assert parse_topic("gutenberg:12345 ch 1") == BookRef("gutenberg", "12345", 1)


def test_bad_topics(home: Path) -> None:
    """UT-MKT-018.002.M02.T02: A web link, a path, a bad type or free text fail at once."""
    for topic in ("https://x.com/b.pdf ch 1", "upload:../a.txt ch 1", "upload:a.exe ch 1",
                  "Read chapter 2"):
        assert parse_topic(topic) is None
        res = _skill().step(FakeCtx(home, None), _ticket(topic))
        assert res is not None and res.outcome == "failed" and "topic form" in res.note


def test_gutenberg_once(tmp_path: Path) -> None:
    """UT-MKT-018.003.M02.T01: One download from gutenberg.org, cached, licence cut off."""
    calls: list[str] = []

    def get(url: str) -> str:
        calls.append(url)
        return "Licence header\n*** START OF THE BOOK ***\nBody text\n*** END OF THE BOOK ***\nfooter"

    ref = BookRef("gutenberg", "12345", 1)
    first = load_text(ref, tmp_path, get)
    second = load_text(ref, tmp_path, get)
    assert calls == [GUTENBERG_URL.format(n="12345")]
    assert first == second and "Body text" in first
    assert "Licence" not in first and "footer" not in first
    assert (tmp_path / "gutenberg-12345.txt").is_file()


def test_missing_or_failed(tmp_path: Path) -> None:
    """UT-MKT-018.003.M02.T02: A missing upload or a failed download fail plainly."""
    calls: list[str] = []
    with pytest.raises(BookError):
        load_text(BookRef("upload", "nope.txt", 1), tmp_path, lambda u: calls.append(u) or "")
    assert calls == []

    def get(url: str) -> str:
        calls.append(url)
        raise OSError("timed out")

    with pytest.raises(BookError):
        load_text(BookRef("gutenberg", "9", 1), tmp_path, get)
    assert calls == [GUTENBERG_URL.format(n="9")]
    with pytest.raises(BookError, match="empty"):
        load_text(BookRef("gutenberg", "8", 1), tmp_path, lambda u: "*** START OF X ***\n\n")
    assert not (tmp_path / "gutenberg-8.txt").exists()
    big = tmp_path / "big.txt"
    with big.open("wb") as out:
        out.truncate(20_000_001)
    with pytest.raises(BookError, match="20 MB"):
        read_file(big)


def _pdf(path: Path, text: str) -> None:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1,
                                                                             xref)
    path.write_bytes(out)


def test_readers(tmp_path: Path) -> None:
    """UT-MKT-018.004.M02.T01: Text, Markdown, HTML and PDF give plain text."""
    (tmp_path / "a.txt").write_text("plain words", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Title\nmark words", encoding="utf-8")
    (tmp_path / "c.html").write_text("<p>web words</p><script>var x = 1;</script>",
                                     encoding="utf-8")
    _pdf(tmp_path / "d.pdf", "pdf words here")
    assert "plain words" in read_file(tmp_path / "a.txt")
    assert "mark words" in read_file(tmp_path / "b.md")
    html = read_file(tmp_path / "c.html")
    assert "web words" in html and "var x" not in html
    assert "pdf words here" in read_file(tmp_path / "d.pdf")


def test_bad_pdf(home: Path) -> None:
    """UT-MKT-018.004.M02.T02: A file named .pdf that is not a PDF fails plainly."""
    (home / "books" / "fake.pdf").write_text("not a pdf at all", encoding="utf-8")
    res = _skill().step(FakeCtx(home, None), _ticket("upload:fake.pdf ch 1"))
    assert res is not None and res.outcome == "failed" and "PDF" in res.note


# ---------------- chapters ----------------

def test_headings() -> None:
    """UT-MKT-018.005.M02.T01: Chapter 2 sits between the 2nd and 3rd heading; contents skipped."""
    text = chapter(BOOK, 2)
    assert text.startswith("CHAPTER II") and "old high" in text and "last lesson" not in text


def test_parts_and_cut() -> None:
    """UT-MKT-018.005.M02.T02: No headings gives 5,000-word parts; long text is cut."""
    words = " ".join(f"w{i}" for i in range(12_000))
    parts = chapters(words)
    assert [len(p.split()) for p in parts] == [5_000, 5_000, 2_000]
    assert len(chapter("x" * 30_000 + " end", 1)) == 24_000


def test_missing_chapter(home: Path) -> None:
    """UT-MKT-018.005.M02.T03: Chapter 9 of a 3-chapter book fails with the count."""
    res = _skill().step(FakeCtx(home, None), _ticket("upload:book.txt ch 9"))
    assert res is not None and res.outcome == "failed" and "only 3 chapter(s)" in res.note


# ---------------- read once ----------------

def test_never_reread(home: Path) -> None:
    """UT-MKT-018.006.M03.T01: A read chapter fails at once and names the card."""
    _run(home, _card())
    (home / "books" / "book.txt").unlink()
    res = _skill().step(FakeCtx(home, None), _ticket(tid=8))
    assert res is not None and res.outcome == "failed"
    assert "read by ticket 7; see card SC-1" in res.note
    res = _skill().step(FakeCtx(home, None), _ticket("upload:BOOK.TXT ch 2", tid=9))
    assert res is not None and res.outcome == "failed" and "see card SC-1" in res.note


def test_other_chapter(home: Path) -> None:
    """UT-MKT-018.006.M03.T02: After chapter 2, chapter 3 may still be read."""
    _run(home, _card())
    res = _skill().step(FakeCtx(home, None), _ticket("upload:book.txt ch 3", tid=8))
    assert res is not None and res.outcome == "go"
    assert already_read(home, "upload:book.txt", 3) is None


# ---------------- card ----------------

def test_answer_limits() -> None:
    """UT-MKT-018.007.M01.T01: Four quotes, a long entry or no quote are not valid."""
    base = _card().model_dump()
    for change in ({"quotes": ["q" * 20] * 4}, {"entry": "x" * 301}, {"quotes": []}):
        with pytest.raises(ValidationError):
            StrategyCard.model_validate({**base, **change})


def test_quotes_checked(home: Path) -> None:
    """UT-MKT-018.008.M01.T01: Spacing and curly quotes are fine; made-up quotes dropped."""
    quotes = ["Buy when the price  breaks above\nthe old high", "Sell half at twice the risk",
              "Always buy on Mondays at the open"]
    assert found_quotes(quotes, BOOK) == quotes[:2]
    curly = ["Don’t chase the move ever"]
    assert found_quotes(curly, "Rule one: don't chase the move ever.") == curly
    steps = _run(home, _card(quotes=quotes))
    assert "Quotes kept: 2 of 3" in steps[1].note
    stored = _rows(home, "SELECT source, chapter, ticket_id, quotes FROM strategy_cards")
    assert stored[0][:3] == ("upload:book.txt", 2, 7) and len(json.loads(stored[0][3])) == 2
    assert _rows(home, "SELECT source, chapter, card_id FROM books_read") == [
        ("upload:book.txt", 2, 1)]


def test_no_quote_found(home: Path) -> None:
    """UT-MKT-018.008.M01.T02: Only made-up quotes still save the card and mark it read."""
    steps = _run(home, _card(quotes=["Always buy on Mondays at the open"]))
    assert "Quotes kept: 0 of 1" in steps[1].note and steps[1].gain is False
    assert already_read(home, "upload:book.txt", 2) is not None


def test_gain_yes(home: Path) -> None:
    """UT-MKT-018.009.M01.T01: Entry, exit, stop and a found quote make the gain yes."""
    last = _run(home, _card())[1]
    assert last.gain is True and last.outcome == "done"
    assert "Card SC-1: Volume breakout" in last.note and "Stop: Below the breakout" in last.note


def test_gain_no(home: Path) -> None:
    """UT-MKT-018.009.M01.T02: A blank stop makes the gain no; still done."""
    last = _run(home, _card(stop=""))[1]
    assert last.gain is False and last.outcome == "done"


# ---------------- lead block ----------------

def test_lead_books_block(p5b: Env) -> None:
    """UT-MKT-018.010.M03.T01: The lead's facts list uploads, the topic form and reads."""
    folder = p5b.home / "books"
    folder.mkdir()
    for name in ("alpha.pdf", "beta.txt", "gutenberg-9.txt", "notes.docx"):
        (folder / name).write_text("x", encoding="utf-8")
    save_card(p5b.home, "upload:beta.txt", 2, 7, CardText("n", "i", "", "", "", "", []), "x")
    text = _stage(p5b).facts(p5b.home).text
    assert "upload:alpha.pdf" in text and "upload:beta.txt" in text
    assert "gutenberg:<number> ch <n>" in text and "docx" not in text
    assert "Already read: upload:beta.txt ch 2 (card SC-1)" in text


def test_books_empty_and_limit(tmp_path: Path) -> None:
    """UT-MKT-018.010.M03.T02: No folder says so; many uploads stop at 15 lines."""
    assert "No uploaded books yet" in books_block(tmp_path, tmp_path / "books")
    folder = tmp_path / "books"
    folder.mkdir()
    for i in range(20):
        (folder / f"b{i:02d}.txt").write_text("x", encoding="utf-8")
    save_card(tmp_path, "upload:b00.txt", 1, 3, CardText("n", "i", "", "", "", "", []), "x")
    lines = books_block(tmp_path, folder).splitlines()
    assert len(lines) <= 15 and lines[-1].startswith("Already read: upload:b00.txt ch 1")


# ---------------- employee and logs ----------------

def test_default_employee() -> None:
    """UT-MKT-018.011.M01.T01: emp-016 ships with skill book_to_strategy and a loadable path."""
    folders = {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}
    hire = load_employee(folders["emp-016"], SKILL_PATHS)
    assert hire is not None
    assert (hire.spec.level, hire.spec.skill, hire.spec.trigger) == (
        "expert", "book_to_strategy", ("research_done",))
    assert isinstance(hire.skill, BookStrategySkill)


def test_never_wakes(tmp_path: Path) -> None:
    """UT-MKT-018.011.M01.T02: Events never wake the book employee."""
    skill = _skill()
    facts = skill.facts(tmp_path)
    assert not facts.fresh and skill.act(FakeCtx(tmp_path, None), facts) == []


def test_logs(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-018.012.M01.T01: Steps log book, chapter, words and quotes kept."""
    caplog.set_level(logging.INFO, logger="us_swing.market.book_strategy")
    _run(home, _card())
    assert "[Research] Ticket 7 read chapter 2 of upload:book.txt (140 words)" in caplog.text
    assert "[Research] Ticket 7 saved card SC-1, 1 of 1 quotes found" in caplog.text
