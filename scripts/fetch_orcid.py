"""Fetch the public ORCID record and DOI metadata into data/orcid_cache.json.

If ORCID or a DOI lookup fails, the previous cache entry is kept so a
scheduled build never publishes an emptier site than the last one.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "orcid_cache.json"
PROFILE = ROOT / "config" / "profile.yaml"
UA = "personal-homepage-builder (https://github.com/jcy1102)"


def get_json(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def normalize_doi(doi):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I)


def abbreviate_author(a):
    """'Woo-Hyun Jeon' -> 'Jeon W-H'; 'Soo Min Song' -> 'Song SM'."""
    family = (a.get("family") or a.get("literal") or "").strip()
    given = (a.get("given") or "").strip()
    if not given:
        return family
    parts = []
    for word in given.split():
        parts.append("-".join(p[0].upper() for p in word.split("-") if p))
    return f"{family} {''.join(parts)}"


def is_owner(a, owner):
    return (a.get("family") or "").strip().lower() == owner["family"].lower() and (
        a.get("given") or ""
    ).strip().lower().replace("-", "").startswith(owner["given"].lower())


def year_of(date):
    return int(date["year"]["value"]) if date and date.get("year") else None


def affiliations(summary, section, key):
    rows = []
    for group in (summary.get(section) or {}).get("affiliation-group", []):
        for s in group["summaries"]:
            e = s[key]
            rows.append(
                {
                    "org": e["organization"]["name"],
                    "department": e.get("department-name"),
                    "role": e.get("role-title"),
                    "start": year_of(e.get("start-date")),
                    "end": year_of(e.get("end-date")),
                }
            )
    return rows


def csl_for(doi):
    return get_json("https://doi.org/" + doi, accept="application/vnd.citationstyles.csl+json")


def work_from(summary, csl, owner):
    ext = (summary.get("external-ids") or {}).get("external-id", [])
    doi = next((normalize_doi(x["external-id-value"]) for x in ext if x["external-id-type"] == "doi"), None)
    pub_date = summary.get("publication-date") or {}
    work = {
        "doi": doi,
        "type": summary.get("type"),
        "title": summary["title"]["title"]["value"],
        "journal": (summary.get("journal-title") or {}).get("value") or "",
        "year": year_of(pub_date),
        "date": [year_of(pub_date) or 0],
        "volume": None,
        "issue": None,
        "pages": None,
        "authors": [],
    }
    if csl:
        parts = (csl.get("issued") or {}).get("date-parts") or [[None]]
        container = csl.get("container-title") or ""
        if isinstance(container, list):
            container = container[0] if container else ""
        title = csl.get("title") or work["title"]
        if isinstance(title, list):
            title = title[0]
        work.update(
            title=re.sub(r"<[^>]+>", "", title).strip(),
            journal=container or work["journal"],
            year=parts[0][0] or work["year"],
            date=[p for p in parts[0] if p] or work["date"],
            volume=csl.get("volume"),
            issue=csl.get("issue"),
            pages=csl.get("page") or csl.get("article-number"),
            authors=[{"name": abbreviate_author(a), "me": is_owner(a, owner)} for a in csl.get("author", [])],
        )
    return work


def main():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    orcid = profile["orcid"]
    owner = profile["owner_match"]
    old = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    old_works = {w["doi"]: w for w in old.get("works", []) if w.get("doi")}

    try:
        record = get_json(f"https://pub.orcid.org/v3.0/{orcid}/record")
    except Exception as e:  # keep the last good site
        print(f"WARNING: ORCID fetch failed ({e}); keeping cached data.")
        return 0

    acts = record["activities-summary"]
    works, failed = [], []
    for group in acts["works"]["group"]:
        summary = group["work-summary"][0]
        ext = (summary.get("external-ids") or {}).get("external-id", [])
        doi = next((normalize_doi(x["external-id-value"]) for x in ext if x["external-id-type"] == "doi"), None)
        csl = None
        if doi:
            try:
                csl = csl_for(doi)
            except Exception as e:
                failed.append(f"{doi} ({e})")
        if csl is None and doi in old_works:
            works.append(old_works[doi])
            continue
        works.append(work_from(summary, csl, owner))

    data = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "orcid": orcid,
        "educations": affiliations(acts, "educations", "education-summary"),
        "employments": affiliations(acts, "employments", "employment-summary"),
        "qualifications": affiliations(acts, "qualifications", "qualification-summary"),
        "works": works,
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ORCID: {len(works)} works, {len(data['educations'])} educations, {len(data['employments'])} employments")
    for f in failed:
        print(f"WARNING: DOI lookup failed: {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
