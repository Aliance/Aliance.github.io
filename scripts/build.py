#!/usr/bin/env python3
"""Генератор lesnykh.ru.

Источник данных: data/cv.json. Шаблоны: templates/.
Результат: index.html, en/cv/index.html, ru/cv/index.html (редирект), resume.json,
resume.ru.json, ilia-lesnykh.vcf, llms.txt, sitemap.xml, robots.txt, assets/og-*.png
и resume-*.pdf (две последние группы требуют Google Chrome; флаг --no-chrome их пропускает).

Запуск: python3 scripts/build.py [--no-chrome]
"""
import datetime
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "cv.json"
TEMPLATES = ROOT / "templates"
BUILD_DIR = ROOT / ".build"
LANGS = ("ru", "en")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


# ---------------------------------------------------------------------------
# Мини-шаблонизатор: подмножество Twig.
#   {{ path }}            значение с HTML-экранированием
#   {{ path|raw }}        без экранирования
#   {% for x in path %} … {% endfor %}      внутри доступен loop.index / loop.first / loop.last
#   {% if path %} … {% else %} … {% endif %}  также {% if not path %}
# ---------------------------------------------------------------------------
TOKEN = re.compile(r"{{\s*(.*?)\s*}}|{%\s*(.*?)\s*%}", re.S)


def lookup(ctx, path):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)) and part.isdigit():
            cur = cur[int(part)]
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def parse(src):
    root, stack, pos = [], [], 0
    stack.append(root)
    for m in TOKEN.finditer(src):
        if m.start() > pos:
            stack[-1].append(["text", src[pos:m.start()]])
        pos = m.end()
        if m.group(1) is not None:
            stack[-1].append(["var", m.group(1)])
            continue
        tag = m.group(2).split()
        if tag[0] == "for":
            node = ["for", tag[1], tag[3], []]
            stack[-1].append(node)
            stack.append(node[3])
        elif tag[0] == "if":
            node = ["if", " ".join(tag[1:]), [], []]
            stack[-1].append(node)
            stack.append(node[2])
        elif tag[0] == "else":
            stack.pop()
            stack.append(stack[-1][-1][3])
        elif tag[0] in ("endif", "endfor"):
            stack.pop()
        else:
            raise ValueError(f"unknown tag: {tag}")
    if pos < len(src):
        stack[-1].append(["text", src[pos:]])
    return root


def render(nodes, ctx):
    out = []
    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(node[1])
        elif kind == "var":
            expr, _, flt = node[1].partition("|")
            value = lookup(ctx, expr.strip())
            text = "" if value is None else str(value)
            out.append(text if flt.strip() == "raw" else html.escape(text, quote=True))
        elif kind == "if":
            cond = node[1]
            negate = cond.startswith("not ")
            value = lookup(ctx, cond[4:].strip() if negate else cond)
            out.append(render(node[2] if bool(value) != negate else node[3], ctx))
        elif kind == "for":
            items = lookup(ctx, node[2]) or []
            for i, item in enumerate(items):
                sub = dict(ctx)
                sub[node[1]] = item
                sub["loop"] = {"index": i + 1, "first": i == 0, "last": i == len(items) - 1}
                out.append(render(node[3], sub))
    return "".join(out)


def render_file(name, ctx):
    return render(parse((TEMPLATES / name).read_text(encoding="utf-8")), ctx)


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------
def L(value, lang):
    """Разворачивает {"ru": …, "en": …} в значение для языка, рекурсивно."""
    if isinstance(value, dict):
        if set(value) == set(LANGS):
            return L(value[lang], lang)
        return {k: L(v, lang) for k, v in value.items()}
    if isinstance(value, list):
        return [L(v, lang) for v in value]
    return value


def ym(text):
    year, month = text.split("-")
    return int(year), int(month)


def years_since(start, today):
    year, month = ym(start)
    return today.year - year - (1 if today.month < month else 0)


def period_html(job, ui):
    months = ui["months"]
    y1, m1 = ym(job["start"])
    if not job.get("end"):
        return f"{months[m1 - 1]} {y1} —<br>{ui['now']}"
    y2, m2 = ym(job["end"])
    if y1 == y2:
        return f"{months[m1 - 1]} — {months[m2 - 1]}<br>{y1}"
    return f"{months[m1 - 1]} {y1} —<br>{months[m2 - 1]} {y2}"


def chips(items, tones):
    return [{"name": name, "tone": tones.get(name, "")} for name in items]


def clean(obj):
    """Убирает None и пустые списки, чтобы JSON Resume оставался валидным."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if v is not None and v != []}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def full_name(basics):
    return f'{basics["first_name"]} {basics["last_name"]}'


def page_context(data, lang, years, today):
    site = data["site"]
    base = site["url"].rstrip("/")
    pages = site["pages"]
    page = pages[lang]
    other = "en" if lang == "ru" else "ru"
    ui = data["ui"][lang]
    fmt = lambda s: s.replace("{years}", str(years))  # noqa: E731

    basics = L(data["basics"], lang)
    work = L(data["work"], lang)
    current = work[0]
    rel = "../" * page["file"].count("/")
    y, m = ym(current["start"])

    jobs = [{
        "company": j["company"], "url": j.get("url"), "position": j["position"], "summary": j["summary"],
        "start": j["start"], "current": not j.get("end"),
        "period": period_html(j, ui), "stack": chips(j["stack"], site["tones"]),
    } for j in work]

    contacts = [{"label": "email", "text": basics["email"], "href": "mailto:" + basics["email"], "icon": "mail"}]
    contacts += [{"label": p["network"].lower(), "text": p["username"], "href": p["url"], "icon": p["icon"]}
                 for p in basics["profiles"]]

    stats = [{
        "big": fmt(s["big"]), "text": s["text"], "label": fmt(s["label"]),
        "small": s.get("small", False), "hot": s.get("hot", False),
    } for s in L(data["stats"], lang)]

    skills = [{"label": g["label"], "chips": chips(g["items"], site["tones"])} for g in L(data["skills"], lang)]

    edu_items = [{"name": f'{e["institution"]} · {e["studyType"]}', "label": f'{e["start"]} — {e["end"]} · {e["area"]}'}
                 for e in L(data["education"], lang)]
    edu_items += [{"name": c["name"], "label": c["label"]} for c in L(data["certificates"], lang)]

    name = full_name(basics)
    page_url = base + page["path"]
    return {
        "lang": lang, "is_ru": lang == "ru", "ui": ui, "rel": rel,
        "title": L(site["title"], lang), "description": L(site["description"], lang),
        "og_title": f'{name} — {basics["label"]}',
        "page_url": page_url, "url_ru": base + pages["ru"]["path"], "url_en": base + pages["en"]["path"],
        "switch_href": (rel + pages[other]["path"].lstrip("/")) if lang == "ru" else rel,
        "alt_locale": data["ui"][other]["locale"],
        "og_image_url": f'{base}/{page["og"]}',
        "resume_json": page["resume_json"], "pdf": page["pdf"], "vcard": site["vcard"], "avatar": site["avatar"],
        "avatar_abs": (ROOT / site["avatar"]).as_uri(),
        "name": name, "first_name": basics["first_name"], "last_name": basics["last_name"],
        "role": basics["role"], "company_lc": current["company"].lower(), "city_lc": basics["city"].lower(),
        "status": f'{ui["status"]} {ui["months_gen"][m - 1]} {y}',
        "floats": [fmt(f) for f in basics["floats"]],
        "contacts": contacts,
        "statement": basics["statement"], "statement_accent": basics["statement_accent"], "summary": basics["summary"],
        "stats": stats, "skills": skills, "edu_items": edu_items,
        "jobs": jobs, "jobs_count": len(jobs), "first_year": ym(work[-1]["start"])[0],
        "since": site["since"], "year": today.year, "metrika": site["metrika"],
        "site_label": page_url.split("//", 1)[1].rstrip("/") if lang == "ru" else page_url.split("//", 1)[1],
        "jsonld": json.dumps(jsonld(data, lang, basics, current), ensure_ascii=False).replace("<", "\\u003c"),
    }


def jsonld(data, lang, basics, current):
    site = data["site"]
    base = site["url"].rstrip("/")
    schools = []
    for e in L(data["education"], lang):
        entry = {"@type": "CollegeOrUniversity", "name": e["institution"], "url": e.get("url")}
        if entry not in schools:
            schools.append(entry)
    return clean({
        "@context": "https://schema.org",
        "@type": "Person",
        "name": full_name(basics),
        "givenName": basics["first_name"],
        "familyName": basics["last_name"],
        "jobTitle": basics["label"],
        "worksFor": {"@type": "Organization", "name": current["company"], "url": current.get("url")},
        "email": "mailto:" + basics["email"],
        "telephone": basics["phone_e164"],
        "url": base + site["pages"][lang]["path"],
        "image": f'{base}/{site["avatar"]}',
        "address": {"@type": "PostalAddress", "addressLocality": basics["city"], "addressCountry": basics["country_code"]},
        "alumniOf": schools,
        "knowsAbout": [k for g in L(data["skills"], lang) for k in g["items"]],
        "sameAs": [p["url"] for p in basics["profiles"] if p.get("same_as")],
    })


def json_resume(data, lang, today):
    site = data["site"]
    base = site["url"].rstrip("/")
    page = site["pages"][lang]
    basics = L(data["basics"], lang)
    ui = data["ui"][lang]
    return clean({
        "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json",
        "basics": {
            "name": full_name(basics),
            "label": basics["label"],
            "image": f'{base}/{site["avatar"]}',
            "email": basics["email"],
            "phone": basics["phone"],
            "url": base + page["path"],
            "summary": f'{basics["statement"]} {basics["statement_accent"]} {basics["summary"]}',
            "location": {"city": basics["city"], "countryCode": basics["country_code"]},
            "profiles": [{"network": p["network"], "username": p["username"], "url": p["url"]} for p in basics["profiles"]],
        },
        "work": [{
            "name": j["company"], "url": j.get("url"), "position": j["position"],
            "startDate": j["start"], "endDate": j.get("end"), "summary": j["summary"],
            "highlights": [f'{ui["stack"]}: {", ".join(j["stack"])}'],
        } for j in L(data["work"], lang)],
        "education": [{
            "institution": e["institution"], "url": e.get("url"), "area": e["area"], "studyType": e["studyType"],
            "startDate": e["start"], "endDate": e["end"],
        } for e in L(data["education"], lang)],
        "certificates": [{"name": c["name"], "issuer": c.get("issuer"), "url": c.get("url")} for c in L(data["certificates"], lang)],
        "skills": [{"name": g["label"], "keywords": g["items"]} for g in L(data["skills"], lang)],
        "meta": {"canonical": f'{base}/{page["resume_json"]}', "lastModified": today.isoformat(), "language": lang},
    })


def vcard(data, today):
    site = data["site"]
    basics = L(data["basics"], "en")
    current = L(data["work"][0], "en")
    lines = [
        "BEGIN:VCARD", "VERSION:3.0",
        f'N:{basics["last_name"]};{basics["first_name"]};;;',
        f"FN:{full_name(basics)}",
        f'ORG:{current["company"]}',
        f'TITLE:{basics["label"]}',
        f'EMAIL;TYPE=INTERNET:{basics["email"]}',
        f'TEL;TYPE=CELL:{basics["phone_e164"]}',
        f'ADR;TYPE=HOME:;;;{basics["city"]};;;{basics["country"]}',
        f'URL:{site["url"].rstrip("/")}/',
    ]
    lines += [f'X-SOCIALPROFILE;TYPE={p["network"].lower()}:{p["url"]}' for p in basics["profiles"] if p.get("same_as")]
    lines += [f"REV:{today.isoformat()}", "END:VCARD"]
    return "\r\n".join(lines) + "\r\n"


def llms_txt(data, years):
    site = data["site"]
    base = site["url"].rstrip("/")
    pages = site["pages"]
    basics = L(data["basics"], "en")
    work = L(data["work"], "en")
    out = [
        f"# {full_name(basics)}",
        "",
        f'> {basics["label"]} at {work[0]["company"]}. {basics["statement"]} {basics["summary"]} {basics["city"]}, {basics["country"]}.',
        "",
        "## Pages",
        f'- [CV in English]({base}{pages["en"]["path"]})',
        f'- [Резюме на русском]({base}{pages["ru"]["path"]})',
        f'- [Resume PDF, English]({base}/{pages["en"]["pdf"]})',
        f'- [Резюме PDF, русский]({base}/{pages["ru"]["pdf"]})',
        f'- [JSON Resume, English]({base}/{pages["en"]["resume_json"]})',
        f'- [JSON Resume, Russian]({base}/{pages["ru"]["resume_json"]})',
        "",
        "## Contacts",
        f'- Email: {basics["email"]}',
    ]
    out += [f'- {p["network"]}: {p["url"]}' for p in basics["profiles"]]
    out += ["", f"## Experience ({years}+ years)"]
    for j in work:
        end = j.get("end") or "present"
        out.append(f'- {j["start"]} — {end}: {j["company"]}, {j["position"]}. {j["summary"]} Stack: {", ".join(j["stack"])}.')
    out += ["", "## Education"]
    out += [f'- {e["start"]} — {e["end"]}: {e["institution"]}, {e["studyType"]}, {e["area"]}' for e in L(data["education"], "en")]
    out += [f'- {c["name"]}: {c["label"]}' for c in L(data["certificates"], "en")]
    out += ["", "## Skills"]
    out += [f'- {g["label"]}: {", ".join(g["items"])}' for g in L(data["skills"], "en")]
    return "\n".join(out) + "\n"


def sitemap(data, today):
    base = data["site"]["url"].rstrip("/")
    urls = "".join(
        f"    <url>\n        <loc>{base}{p['path']}</loc>\n        <lastmod>{today.isoformat()}</lastmod>\n    </url>\n"
        for p in data["site"]["pages"].values()
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def robots(data):
    return f'User-agent: *\nDisallow:\nSitemap: {data["site"]["url"].rstrip("/")}/sitemap.xml\n'


def redirect_page(data):
    base = data["site"]["url"].rstrip("/")
    ui = data["ui"]["ru"]
    return (
        '<!DOCTYPE html>\n<html lang="ru">\n<head>\n'
        '    <meta charset="utf-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '    <title>Илья Лесных — резюме переехало на главную</title>\n'
        f'    <link rel="canonical" href="{base}/">\n'
        '    <meta http-equiv="refresh" content="0; url=../../">\n'
        "    <script>location.replace('../../');</script>\n"
        '</head>\n<body>\n'
        f'    <p>{ui["moved"]} <a href="../../">lesnykh.ru</a>.</p>\n'
        '</body>\n</html>\n'
    )


# ---------------------------------------------------------------------------
# Chrome: OG-картинки и PDF
# ---------------------------------------------------------------------------
def chrome(profile, *args):
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         f"--user-data-dir={profile}", "--hide-scrollbars", "--virtual-time-budget=8000", *args],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def write(path, text, binary=False):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    print(f"ok: {path.relative_to(ROOT)}")


def main():
    no_chrome = "--no-chrome" in sys.argv
    data = json.loads(DATA.read_text(encoding="utf-8"))
    today = datetime.date.today()
    years = years_since(data["work"][-1]["start"], today)
    contexts = {lang: page_context(data, lang, years, today) for lang in LANGS}

    for lang, ctx in contexts.items():
        page = data["site"]["pages"][lang]
        write(page["file"], render_file("page.html", ctx))
        write(page["resume_json"], json.dumps(json_resume(data, lang, today), ensure_ascii=False, indent=2) + "\n")

    write("ru/cv/index.html", redirect_page(data))
    write(data["site"]["vcard"], vcard(data, today))
    write("llms.txt", llms_txt(data, years))
    write("sitemap.xml", sitemap(data, today))
    write("robots.txt", robots(data))

    if no_chrome:
        print("skip: og images and pdf (--no-chrome)")
        return
    if not pathlib.Path(CHROME).exists():
        print(f"skip: og images and pdf (Chrome not found at {CHROME}; set CHROME=/path/to/chrome)")
        return

    BUILD_DIR.mkdir(exist_ok=True)
    profile = tempfile.mkdtemp(prefix="lesnykh-chrome-")
    try:
        for lang, ctx in contexts.items():
            page = data["site"]["pages"][lang]
            og_html = BUILD_DIR / f"og-{lang}.html"
            og_html.write_text(render_file("og.html", ctx), encoding="utf-8")
            chrome(profile, "--window-size=1200,630", f"--screenshot={ROOT / page['og']}", og_html.as_uri())
            print(f"ok: {page['og']}")
            chrome(profile, "--no-pdf-header-footer", f"--print-to-pdf={ROOT / page['pdf']}", (ROOT / page["file"]).as_uri())
            print(f"ok: {page['pdf']}")
    finally:
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
