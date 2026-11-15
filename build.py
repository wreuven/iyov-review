#!/usr/bin/env python3
"""Build index.html from guide.txt (intro + Q&A study guide for the Book of Job)."""
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "guide.txt"
TPL = HERE / "template.html"
OUT = HERE / "index.html"

TEACHER = "**דף המורה** · "


def inline(t):
    t = html.escape(t, quote=False).replace("&lt;br&gt;", "<br>")
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t


def parse(text):
    meta, parts, quiz = {}, [], None
    cur = None
    for raw in text.splitlines():
        ln = raw.rstrip()
        if not ln:
            continue
        if m := re.match(r"^@(title|subtitle|lead) (.*)$", ln):
            meta[m.group(1)] = m.group(2)
        elif m := re.match(r"^@part (\S+) \| (.+?) \| (.+)$", ln):
            cur = {"id": m.group(1), "title": m.group(2), "chapters": m.group(3), "intro": [], "qs": []}
            parts.append(cur)
        elif m := re.match(r"^@quiz (.*)$", ln):
            quiz = {"title": m.group(1), "items": []}
            cur = None
        elif ln.startswith("Q: "):
            q = ln[3:]
            teacher = q.startswith(TEACHER)
            cur["qs"].append({"q": q[len(TEACHER):] if teacher else q, "a": "", "teacher": teacher})
        elif ln.startswith("A: "):
            cur["qs"][-1]["a"] = ln[3:]
        elif quiz is not None and cur is None:
            v, who, meaning = [x.strip() for x in ln.split("|")]
            quiz["items"].append((v, who, meaning))
        else:
            cur["intro"].append(ln)
    return meta, parts, quiz


def build():
    meta, parts, quiz = parse(SRC.read_text(encoding="utf-8"))
    body, toc = [], []
    total = 0
    for p in parts:
        toc.append(f'<li><a href="#{p["id"]}" data-toc="{p["id"]}"><span class="tch">{html.escape(p["chapters"])}</span>'
                   f'<span class="tt">{inline(p["title"])}</span><span class="tc" data-count="{p["id"]}"></span></a></li>')
        out = [f'<section class="part" id="{p["id"]}" data-part="{p["id"]}">',
               f'<header class="part-head"><span class="chips">{html.escape(p["chapters"])}</span><h2>{inline(p["title"])}</h2></header>',
               '<div class="intro">' + "".join(f"<p>{inline(x)}</p>" for x in p["intro"]) + "</div>",
               '<ol class="qs">']
        for i, q in enumerate(p["qs"], 1):
            total += 1
            qid = f'{p["id"]}-{i}'
            badge = '<span class="badge">דף המורה</span>' if q["teacher"] else ""
            out.append(
                f'<li class="qcard{" teacher" if q["teacher"] else ""}" data-q="{qid}">'
                f'<div class="qtext"><span class="qn">{i}</span><div>{badge}{inline(q["q"])}</div></div>'
                f'<button class="reveal" type="button">הצגת תשובה</button>'
                f'<div class="ans" hidden><div class="atext">{inline(q["a"])}</div>'
                f'<div class="mark"><button type="button" class="knew">✓ ידעתי</button>'
                f'<button type="button" class="again">↺ לחזור על זה</button></div></div></li>')
        out.append("</ol></section>")
        body.append("\n".join(out))

    if quiz:
        toc.append('<li><a href="#quiz" data-toc="quiz"><span class="tch">חזרה</span><span class="tt">מי אמר?</span><span class="tc"></span></a></li>')
        cards = []
        for v, who, meaning in quiz["items"]:
            cards.append(f'<button type="button" class="qz"><span class="qz-v">״{inline(v)}״</span>'
                         f'<span class="qz-a"><strong>{inline(who)}</strong> · {inline(meaning)}</span></button>')
        body.append(f'<section class="part" id="quiz"><header class="part-head"><span class="chips">חזרה</span><h2>{inline(quiz["title"])}</h2></header>'
                    f'<div class="intro"><p>לחצי על פסוק כדי לראות מי אמר אותו ומה הוא אומר.</p></div>'
                    f'<div class="quiz">{"".join(cards)}</div></section>')

    page = TPL.read_text(encoding="utf-8")
    for k, v in {"{{TITLE}}": inline(meta["title"]), "{{SUBTITLE}}": inline(meta["subtitle"]),
                 "{{LEAD}}": inline(meta["lead"]), "{{TOC}}": "\n".join(toc),
                 "{{BODY}}": "\n".join(body), "{{TOTAL}}": str(total)}.items():
        page = page.replace(k, v)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.name}: {len(parts)} parts, {total} questions, {len(quiz['items']) if quiz else 0} quiz items, {len(page)//1024} KB")


if __name__ == "__main__":
    build()
