"""
Module: MD-GUI-046.007.M03 — API guide web page
Parent SRD: SRD-GUI-046.010

Turns the API guide (the small Markdown set it uses) into one offline HTML page:
left menu with search, coloured code with Copy buttons, light or dark like Windows.
"""
from __future__ import annotations

import html
import keyword
import re

_FENCE = re.compile(r"^(\s*)```(\w*)\s*$")
_HEADING = re.compile(r"^(#{1,3}) (.+)$")
_ORDERED = re.compile(r"^\d+\. (.*)$")
_SIGNATURE = re.compile(r"^(class [A-Za-z_]\w*$|[A-Za-z_][\w.]*\()")
_PY_TOKEN = re.compile(r"""
    (?P<comment>\#[^\n]*)
  | (?P<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
  | (?P<number>\b\d+(?:\.\d+)?\b)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
""", re.X)
_BUILTINS = {"True", "False", "None", "self", "len", "print", "range"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def guide_page(markdown: str, title: str) -> str:
    """The whole HTML page for ``markdown``."""
    body, toc = _blocks(markdown.splitlines())
    menu = "\n".join(
        f'<a class="l{level}" href="#{anchor}">{_inline(text)}</a>' for level, anchor, text in toc)
    return (_PAGE.replace("__TITLE__", html.escape(title)).replace("__MENU__", menu)
            .replace("__BODY__", body))


def _blocks(lines: list[str]) -> tuple[str, list[tuple[int, str, str]]]:
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif _FENCE.match(line):
            code, i = _code(lines, i)
            out.append(code)
        elif heading := _HEADING.match(line):
            level, text = len(heading.group(1)), heading.group(2).strip()
            anchor = slug(text)
            signature = level == 3 and bool(_SIGNATURE.match(text))
            css = ' class="sig"' if signature else ""
            inner = html.escape(text) if signature else _inline(text)
            out.append(f'<h{level} id="{anchor}"{css}>{inner}</h{level}>')
            if level > 1:
                toc.append((level, anchor, text))
            i += 1
        elif line.startswith("|"):
            table, i = _table(lines, i)
            out.append(table)
        elif line.startswith("- ") or _ORDERED.match(line):
            block, i = _list(lines, i)
            out.append(block)
        else:
            para: list[str] = []
            while i < len(lines) and lines[i].strip() and not _starts_block(lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(out), toc


def _starts_block(line: str) -> bool:
    return bool(_FENCE.match(line) or _HEADING.match(line) or line.startswith(("|", "- "))
                or _ORDERED.match(line))


def _code(lines: list[str], i: int) -> tuple[str, int]:
    fence = _FENCE.match(lines[i])
    assert fence is not None
    indent, lang = len(fence.group(1)), fence.group(2) or "text"
    i += 1
    code: list[str] = []
    while i < len(lines) and not _FENCE.match(lines[i]):
        code.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i])
        i += 1
    text = "\n".join(code)
    shown = _python(text) if lang == "python" else html.escape(text)
    block = (f'<div class="code"><div class="bar"><span>{lang}</span>'
             f'<button class="copy" type="button">Copy</button></div>'
             f"<pre><code>{shown}</code></pre></div>")
    return block, i + 1


def _python(code: str) -> str:
    parts: list[str] = []
    last = 0
    for match in _PY_TOKEN.finditer(code):
        parts.append(html.escape(code[last:match.start()]))
        kind, text = match.lastgroup, match.group(0)
        if kind == "name":
            follows = code[match.end():match.end() + 1]
            if keyword.iskeyword(text):
                kind = "kw"
            elif text in _BUILTINS:
                kind = "builtin"
            elif follows == "(":
                kind = "call"
            else:
                kind = ""
        escaped = html.escape(text)
        parts.append(f'<span class="{kind}">{escaped}</span>' if kind else escaped)
        last = match.end()
    parts.append(html.escape(code[last:]))
    return "".join(parts)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table(lines: list[str], i: int) -> tuple[str, int]:
    rows: list[list[str]] = []
    while i < len(lines) and lines[i].startswith("|"):
        rows.append(_cells(lines[i]))
        i += 1
    head, body = rows[0], [r for r in rows[1:] if not all(set(c) <= set("-: ") for c in r)]
    th = "".join(f"<th>{_inline(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody>' \
           f"</table></div>", i


def _list(lines: list[str], i: int) -> tuple[str, int]:
    ordered = bool(_ORDERED.match(lines[i]))
    items: list[str] = []
    while i < len(lines):
        line = lines[i]
        item = _ORDERED.match(line) if ordered else (line[2:] if line.startswith("- ") else None)
        if item is None:
            break
        text = [item.group(1) if isinstance(item, re.Match) else item]
        i += 1
        while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
            text.append(lines[i].strip())
            i += 1
        items.append(f"<li>{_inline(' '.join(text))}</li>")
    tag = "ol" if ordered else "ul"
    return f"<{tag}>{''.join(items)}</{tag}>", i


def _inline(text: str) -> str:
    pieces = re.split(r"(`[^`]+`)", text)
    out: list[str] = []
    for piece in pieces:
        if piece.startswith("`") and piece.endswith("`") and len(piece) > 1:
            out.append(f"<code>{html.escape(piece[1:-1])}</code>")
            continue
        part = html.escape(piece, quote=False)
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", part)
        part = re.sub(r"\[([^\]]+)\]\((#[\w-]+)\)", r'<a href="\2">\1</a>', part)
        out.append(part)
    return "".join(out)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --bg: #ffffff; --side: #f6f7f9; --text: #1f2328; --muted: #59636e; --line: #d8dee4;
  --accent: #0969da; --inline: #eff1f3; --code-bg: #0f1724; --code-text: #e6edf3;
  --kw: #ff7b72; --str: #a5d6ff; --num: #79c0ff; --com: #8b949e; --call: #d2a8ff;
  --builtin: #ffa657; --sig-bg: #f0f6ff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --side: #11161d; --text: #e6edf3; --muted: #9198a1; --line: #30363d;
    --accent: #4493f8; --inline: #262c36; --code-bg: #161b22; --sig-bg: #13233a;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 16px; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 15px/1.6 "Segoe UI", system-ui, sans-serif; }
nav { position: fixed; top: 0; bottom: 0; left: 0; width: 280px; overflow-y: auto;
      background: var(--side); border-right: 1px solid var(--line); padding: 20px 14px; }
nav .brand { font-weight: 700; font-size: 17px; margin: 0 6px 12px; }
nav input { width: 100%; padding: 7px 10px; margin-bottom: 12px; border-radius: 6px;
            border: 1px solid var(--line); background: var(--bg); color: var(--text);
            font: inherit; outline: none; }
nav input:focus { border-color: var(--accent); }
nav a { display: block; color: var(--text); text-decoration: none; border-radius: 6px;
        padding: 3px 8px; font-size: 14px; }
nav a.l2 { font-weight: 600; margin-top: 10px; }
nav a.l3 { padding-left: 20px; color: var(--muted); font-size: 13px;
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
nav a:hover { background: var(--inline); }
nav a.active { background: var(--accent); color: #fff; }
main { margin-left: 280px; max-width: 980px; padding: 28px 48px 120px; }
h1 { font-size: 32px; margin: 0 0 4px; }
h2 { font-size: 24px; margin: 48px 0 12px; padding-bottom: 6px;
     border-bottom: 1px solid var(--line); }
h3 { font-size: 18px; margin: 32px 0 8px; }
h3.sig { font-family: Consolas, "Cascadia Mono", monospace; font-size: 16px;
         background: var(--sig-bg); border-left: 4px solid var(--accent);
         padding: 8px 12px; border-radius: 0 6px 6px 0; word-break: break-word; }
a { color: var(--accent); }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 13.5px;
       background: var(--inline); padding: 1px 5px; border-radius: 4px; }
.code { margin: 12px 0 18px; border-radius: 8px; overflow: hidden; background: var(--code-bg);
        border: 1px solid var(--line); }
.code .bar { display: flex; justify-content: space-between; align-items: center;
             padding: 4px 8px 4px 14px; font-size: 12px; color: var(--com);
             border-bottom: 1px solid rgba(255,255,255,0.08); }
.code button { font: inherit; color: var(--code-text); background: rgba(255,255,255,0.08);
               border: 1px solid rgba(255,255,255,0.15); border-radius: 5px;
               padding: 2px 10px; cursor: pointer; outline: none; }
.code button:hover { background: rgba(255,255,255,0.16); }
.code button.done { color: #3fb950; border-color: #3fb950; }
pre { margin: 0; padding: 14px 16px; overflow-x: auto; }
pre code { background: none; padding: 0; color: var(--code-text); font-size: 13.5px;
           line-height: 1.55; }
.kw { color: var(--kw); } .string { color: var(--str); } .number { color: var(--num); }
.comment { color: var(--com); font-style: italic; } .call { color: var(--call); }
.builtin { color: var(--builtin); }
.table { overflow-x: auto; margin: 12px 0 18px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { border: 1px solid var(--line); padding: 7px 10px; text-align: left;
         vertical-align: top; }
th { background: var(--side); font-weight: 600; }
li { margin: 4px 0; }
@media (max-width: 800px) {
  nav { position: static; width: auto; border-right: none;
        border-bottom: 1px solid var(--line); }
  main { margin-left: 0; padding: 20px 16px 80px; }
}
</style>
</head>
<body>
<nav>
  <div class="brand">__TITLE__</div>
  <input id="search" type="search" placeholder="Search..." autocomplete="off">
  <div id="menu">
__MENU__
  </div>
</nav>
<main>
__BODY__
</main>
<script>
document.querySelectorAll('.code button.copy').forEach(function (button) {
  button.addEventListener('click', function () {
    var text = button.closest('.code').querySelector('code').innerText;
    function done() {
      button.textContent = 'Copied';
      button.classList.add('done');
      setTimeout(function () { button.textContent = 'Copy'; button.classList.remove('done'); },
                 1500);
    }
    var area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    var copied = false;
    try { copied = document.execCommand('copy'); } catch (error) { copied = false; }
    area.remove();
    if (copied) {
      done();
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(done);
    }
  });
});
var links = Array.prototype.slice.call(document.querySelectorAll('#menu a'));
document.getElementById('search').addEventListener('input', function (event) {
  var words = event.target.value.toLowerCase().trim();
  links.forEach(function (link) {
    var section = document.getElementById(link.getAttribute('href').slice(1));
    var text = link.textContent.toLowerCase();
    var next = section.nextElementSibling, body = '';
    while (next && !/^H[23]$/.test(next.tagName)) { body += next.textContent; next = next.nextElementSibling; }
    link.style.display = !words || text.indexOf(words) >= 0
      || body.toLowerCase().indexOf(words) >= 0 ? '' : 'none';
  });
  var head = null, childShown = false;
  links.concat([null]).forEach(function (link) {
    if (link === null || link.classList.contains('l2')) {
      if (head && childShown) { head.style.display = ''; }
      head = link; childShown = false;
    } else if (link.style.display !== 'none') {
      childShown = true;
    }
  });
});
document.getElementById('search').addEventListener('keydown', function (event) {
  if (event.key !== 'Enter') { return; }
  var first = links.find(function (link) { return link.style.display !== 'none'; });
  if (first) { location.hash = first.getAttribute('href'); }
});
var observer = new IntersectionObserver(function (entries) {
  entries.forEach(function (entry) {
    if (!entry.isIntersecting) { return; }
    links.forEach(function (link) {
      link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id);
    });
  });
}, { rootMargin: '0px 0px -75% 0px' });
document.querySelectorAll('main h2, main h3').forEach(function (h) { observer.observe(h); });
</script>
</body>
</html>
"""
