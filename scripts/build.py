"""Build _site/ (index.html, assets, CV PDF) from config/ and data/orcid_cache.json."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from html import escape
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
CV_NAME = "Chanyoung_Jeong_CV.pdf"
GROUPS = ["SCIE", "KCI", "Preprints", "Unclassified"]
TAXA = ["Hydropsyche", "Ephemera", "Ephemeroptera", "Ephemeridae"]


def classify(work, journals):
    if work.get("type") == "preprint":
        return "Preprints"
    name = (work.get("journal") or "").strip().lower()
    for group, names in journals.items():
        if name in {n.strip().lower() for n in names}:
            return group
    return "Unclassified"


def format_authors(authors):
    names = [f"<b>{escape(a['name'])}</b>" if a["me"] else escape(a["name"]) for a in authors]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def italicize_taxa(title):
    return re.sub(r"\b(" + "|".join(TAXA) + r")\b", r"<i>\1</i>", escape(title))


def source_line(w):
    """'Hydrobiologia, 853(12), 3477–3491' style; pages keep an en dash."""
    parts = [w["journal"] or ("SSRN" if "ssrn" in (w.get("doi") or "") else "")]
    vol = w.get("volume")
    if vol:
        parts.append(f"{vol}({w['issue']})" if w.get("issue") else str(vol))
    if w.get("pages"):
        parts.append(str(w["pages"]).replace("-", "–"))
    return ", ".join(p for p in parts if p)


def build_publications(works, journals, warnings):
    groups = {g: [] for g in GROUPS}
    for w in works:
        g = classify(w, journals)
        if g == "Unclassified":
            warnings.append(f"Unclassified journal: '{w['journal']}' ({w.get('doi')}). Add it to config/journals.yaml.")
        if not w.get("authors"):
            warnings.append(f"No author list from DOI metadata: {w.get('doi') or w['title']}")
        groups[g].append(
            {
                "year": w.get("year"),
                "date": w.get("date") or [0],
                "title": Markup(italicize_taxa(w["title"])),
                "authors": Markup(format_authors(w.get("authors", []))),
                "source": source_line(w),
                "doi": w.get("doi"),
                "first": bool(w.get("authors")) and w["authors"][0]["me"],
            }
        )
    out = []
    for g in GROUPS:
        items = sorted(groups[g], key=lambda x: x["date"], reverse=True)
        for i, it in enumerate(items):
            it["no"] = len(items) - i
        if items:
            out.append({"key": g, "items": items})
    return out


def affiliation_rows(rows, texts, warnings):
    out = []
    for r in rows:
        key = f"{r['org']} | {r['department']} | {r['role']}"
        text = texts.get(key)
        if text is None:
            warnings.append(f"No wording for ORCID entry: \"{key}\". Add it to affiliation_text in config/profile.yaml.")
            text = ", ".join(x for x in [r["role"], r["department"], r["org"]] if x)
        span = f"{r['start']}–{r['end'] or ''}" if r["start"] else ""
        if r["start"] and r["end"] == r["start"]:
            span = str(r["start"])
        out.append({"span": span, "start": r["start"] or 0, "end": r["end"] or 9999, "text": text})
    return sorted(out, key=lambda x: (x["end"], x["start"]), reverse=True)


def find_chrome():
    cands = [os.environ.get("CHROME_BIN")]
    cands += [shutil.which(n) for n in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"]]
    cands += [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    return next((c for c in cands if c and Path(c).exists()), None)


def print_pdf(html_path, pdf_path, timeout=180):
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome/Edge not found; set CHROME_BIN to build the CV PDF.")
    # Headless Chrome 154 can write the PDF and then never exit (seen on macOS and on
    # the Linux CI runner), so stop waiting once it reports "bytes written to file" on
    # stdout or stderr, or once the PDF exists and its size has held for a second.
    pdf_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile_dir, tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(
            [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                f"--user-data-dir={profile_dir}", "--virtual-time-budget=15000",
                f"--print-to-pdf={pdf_path}", html_path.as_uri(),
            ],
            stdout=log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + timeout
        written = False
        size, steady_since = -1, None
        while not written and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)
            log.seek(0)
            written = b"bytes written to file" in log.read()
            now_size = pdf_path.stat().st_size if pdf_path.exists() else 0
            if now_size and now_size == size:
                written = time.monotonic() - steady_since >= 1
            else:
                size, steady_since = now_size, time.monotonic()
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        log.seek(0)
        output = log.read().decode(errors="replace")
    if not written and proc.returncode != 0:
        raise RuntimeError(f"Chrome failed or timed out after {timeout}s (exit {proc.returncode}):\n{output[-2000:]}")
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError("CV PDF was not created.")


def main():
    profile = yaml.safe_load((ROOT / "config" / "profile.yaml").read_text(encoding="utf-8"))
    journals = yaml.safe_load((ROOT / "config" / "journals.yaml").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "data" / "orcid_cache.json").read_text(encoding="utf-8"))
    warnings = []
    texts = profile.get("affiliation_text", {})

    ctx = {
        "p": profile,
        "orcid": data["orcid"],
        "updated": data["fetched_at"],
        "timeline": affiliation_rows(data["educations"] + data["employments"], texts, warnings),
        "education": affiliation_rows(data["educations"], texts, []),
        "experience": affiliation_rows(data["employments"], texts, []),
        "licenses": affiliation_rows(data["qualifications"], texts, warnings),
        "pubs": build_publications(data["works"], journals, warnings),
        # date query makes browsers fetch the new PDF after each ORCID update
        "cv_file": f"assets/{CV_NAME}?v={data['fetched_at']}",
    }
    ctx["n_pubs"] = sum(len(g["items"]) for g in ctx["pubs"])
    ctx["n_first"] = sum(w["first"] for g in ctx["pubs"] for w in g["items"])

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    (OUT / "index.html").write_text(env.get_template("index.html.j2").render(**ctx), encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        cv_html = Path(tmp) / "cv.html"
        cv_html.write_text(env.get_template("cv.html.j2").render(**ctx), encoding="utf-8")
        print_pdf(cv_html, OUT / "assets" / CV_NAME)

    print(f"Built {OUT} with {ctx['n_pubs']} publications (ORCID data from {ctx['updated']}).")
    for w in warnings:
        print("WARNING:", w)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and warnings:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Homepage build warnings\n" + "".join(f"- {w}\n" for w in warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
