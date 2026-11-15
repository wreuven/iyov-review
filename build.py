#!/usr/bin/env python3
"""Build index.html from source.md (the Job exam study guide)."""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "source.md"
OUT = HERE / "index.html"


def inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t


def blocks(lines):
    """Group lines into (kind, payload) blocks."""
    out, para = [], []
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln:
            i += 1
            continue
        if m := re.match(r"^(#{1,3}) (.*)$", ln):
            out.append(("h" + str(len(m.group(1))), m.group(2)))
        elif ln.startswith("- "):
            out.append(("li", ln[2:]))
        elif m := re.match(r"^(\d+)\. (.*)$", ln):
            out.append(("oli", m.group(2)))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"-+", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(("table", rows))
            continue
        else:
            out.append(("p", ln))
        i += 1
    return out


HEB_NUM_RE = re.compile(r"^פרק (\S+) (.*)$")
PART_RE = re.compile(r"^חלק (\S+) (.*)$")


def verse_item(text):
    m = re.match(r"^\*\*([^*]+?) — (״[^*]+?״):\*\*\s*(.*)$", text)
    if not m:
        return None
    ref, quote, expl = m.groups()
    return (f'<li class="verse"><div class="vref">{inline(ref)}</div>'
            f'<blockquote class="vq">{inline(quote)}</blockquote>'
            f'<div class="vexp">{inline(expl)}</div></li>')


def qa(text):
    m = re.match(r"^\*\*(שאלה|שאלת המורה):\*\*\s*(.*?)\s*\*\*(תשובה|תשובה אפשרית):\*\*\s*(.*)$", text)
    if not m:
        return None
    qlabel, q, alabel, a = m.groups()
    return (f'<div class="qa"><div class="q"><span class="tag">{qlabel}</span>{inline(q)}</div>'
            f'<details class="reveal"><summary>הצגת {alabel}</summary><div class="a">{inline(a)}</div></details></div>')


def para(text):
    if r := qa(text):
        return r
    if re.fullmatch(r"\*\*[^*]+\*\*", text):
        inner = text[2:-2]
        teacher = ("המורה" in inner or "הדף" in inner or "דפי" in inner) and not inner.startswith("פסוקים מרכזיים")
        cls = "sub teacher" if teacher else "sub"
        badge = '<span class="badge">מדף המורה</span>' if teacher else ""
        return f'<h4 class="{cls}">{badge}{inline(inner)}</h4>'
    if text.startswith("**למבחן"):
        return f'<div class="callout exam"><span class="ico" aria-hidden="true">✎</span><p>{inline(text)}</p></div>'
    if text.startswith(("**הבחנה חשובה", "**הערת מיקוד", "**הדגש:")):
        return f'<div class="callout note"><p>{inline(text)}</p></div>'
    return f"<p>{inline(text)}</p>"


def slug(i):
    return f"s{i}"


def build():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    first_h1 = next(i for i, l in enumerate(lines) if l.startswith("# "))
    intro = [l for l in lines[:first_h1] if l.strip()]
    body = blocks(lines[first_h1:])

    toc = []          # (level, id, label, short)
    parts_html = []
    open_tags = []    # stack of closing tags
    list_open = None
    sec_n = 0

    def close_list():
        nonlocal list_open
        if list_open:
            parts_html.append(f"</{list_open.split()[0]}>")
            list_open = None

    def close_to(level):
        # level: 1 part, 2 chapter, 3 details
        close_list()
        while open_tags and open_tags[-1][0] >= level:
            parts_html.append(open_tags.pop()[1])

    for kind, val in body:
        if kind == "h1":
            close_to(1)
            sec_n += 1
            sid = slug(sec_n)
            if m := PART_RE.match(val):
                letter, title = m.groups()
                parts_html.append(f'<section class="part" id="{sid}"><h2 class="part-title"><span class="part-no">חלק {letter}׳</span>{inline(title)}</h2>')
                toc.append((1, sid, title, f"חלק {letter}׳"))
            else:
                extra = " selfcheck" if "בדיקה עצמית" in val else (" sources" if "מקורות" in val else "")
                parts_html.append(f'<section class="part{extra}" id="{sid}"><h2 class="part-title plain">{inline(val)}</h2>')
                toc.append((1, sid, val, ""))
            open_tags.append((1, "</section>"))
        elif kind == "h2":
            close_to(2)
            sec_n += 1
            sid = slug(sec_n)
            m = HEB_NUM_RE.match(val)
            num, title = (m.groups() if m else ("", val))
            parts_html.append(
                f'<article class="chapter" id="{sid}" data-ch="{sid}"><header class="ch-head">'
                f'<span class="ch-num">{html.escape(num)}</span><h3>{inline(title)}</h3>'
                f'<label class="done"><input type="checkbox" data-done="{sid}"><span>סיימתי</span></label></header>')
            open_tags.append((2, "</article>"))
            toc.append((2, sid, title, num))
        elif kind == "h3":
            close_to(3)
            label = "העמקה ותרגול" if val.startswith("העמקה ותרגול") else val
            parts_html.append(f'<details class="deep"><summary><span>{inline(label)}</span><span class="hint">לפתיחה</span></summary><div class="deep-body">')
            open_tags.append((3, "</div></details>"))
        elif kind in ("li", "oli"):
            tag = "ul" if kind == "li" else "ol"
            is_verse = kind == "li" and verse_item(val)
            want = ("ul class=\"verses\"" if is_verse else ("ul class=\"links\"" if "](" in val else tag))
            if list_open != want:
                close_list()
                parts_html.append(f"<{want}>")
                list_open = want
            if is_verse:
                parts_html.append(is_verse)
            elif tag == "ol" and in_selfcheck(open_tags, parts_html):
                parts_html.append(f'<li><label class="chk"><input type="checkbox" data-q="{len(parts_html)}"><span>{inline(val)}</span></label></li>')
            else:
                parts_html.append(f"<li>{inline(val)}</li>")
        elif kind == "table":
            close_list()
            head, *rows = val
            t = ['<div class="table-wrap"><table><thead><tr>']
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            parts_html.append("".join(t))
        else:
            close_list()
            parts_html.append(para(val))
    close_to(0)

    # ---------- intro ----------
    lead, how, timeplan, core, prio = intro
    timeplan_html = time_bar(toc)

    toc_html = ['<ol class="toc">']
    for lvl, sid, label, short in toc:
        if lvl == 1:
            toc_html.append(f'<li class="toc-part"><a href="#{sid}">{(short + " · ") if short else ""}{inline(label)}</a></li>')
        else:
            toc_html.append(f'<li class="toc-ch"><a href="#{sid}" data-toc="{sid}"><span class="tnum">{html.escape(short)}</span><span class="tlabel">{inline(label)}</span><span class="tick" aria-hidden="true">✓</span></a></li>')
    toc_html.append("</ol>")
    n_ch = sum(1 for t in toc if t[0] == 2)

    page = TEMPLATE
    repl = {
        "{{LEAD}}": inline(lead),
        "{{HOW}}": inline(how.replace("**איך לענות על שאלת פסוק?**", "").strip()),
        "{{CORE}}": inline(core.replace("**שאלת היסוד:**", "").strip()),
        "{{PRIO}}": inline(prio.replace("**סדר העדיפויות:**", "").strip()),
        "{{TIMENOTE}}": inline(timeplan.split("**", 2)[-1].split("2 דקות.", 1)[-1].strip()),
        "{{TIMEBAR}}": timeplan_html,
        "{{TOC}}": "\n".join(toc_html),
        "{{NCH}}": str(n_ch),
        "{{BODY}}": "\n".join(parts_html),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({len(page)//1024} KB, {n_ch} chapters)")


def in_selfcheck(open_tags, parts_html):
    for chunk in reversed(parts_html):
        if chunk.startswith('<section class="part'):
            return "selfcheck" in chunk
    return False


SEGMENTS = [  # label, minutes, chapter label to link to (first chapter of the block)
    ("א׳–ג׳", 10, "א׳"), ("ד׳–ז׳", 13, "ד׳"), ("ח׳–ט׳", 10, "ח׳"),
    ("ל״ב–ל״ה", 10, "ל״ב"), ("ל״ח", 7, "ל״ח"), ("מ״ב", 8, "מ״ב"), ("בדיקה", 2, None),
]


def time_bar(toc):
    ch_ids = {short: sid for lvl, sid, _, short in toc if lvl == 2}
    selfcheck = next((sid for lvl, sid, label, _ in toc if lvl == 1 and "בדיקה" in label), "")
    total = sum(m for _, m, _ in SEGMENTS)
    segs = []
    for i, (label, mins, ch) in enumerate(SEGMENTS):
        target = ch_ids.get(ch, selfcheck) if ch else selfcheck
        segs.append(f'<a class="seg" data-seg="{i}" data-min="{mins}" href="#{target}" style="flex:{mins}">'
                    f'<span class="seg-l">{label}</span><span class="seg-m">{mins}′</span></a>')
    return f'<div class="timebar" data-total="{total}">{"".join(segs)}</div>'


TEMPLATE = (HERE / "template.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    build()
