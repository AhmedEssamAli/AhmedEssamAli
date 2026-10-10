#!/usr/bin/env python3
"""Discover senior CX / ops jobs from public, unauthenticated ATS JSON APIs.

Usage: python3 jobs/discover_api.py [--out DIR] [--limit-days 30]
Needs only the stdlib + PyYAML. Employers live in jobs/employers.yaml.
"""
import argparse, csv, html, json, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
TIMEOUT, DELAY = 20, 0.3
HEADERS = {"User-Agent": "Mozilla/5.0 (job-discovery script)", "Accept": "application/json"}

SENIORITY = re.compile(r"\b(director|head|vp|vice president|senior manager|manager|lead|principal|consultant)\b", re.I)
FUNCTION = re.compile(
    r"customer|client|contact cent|call cent|\bcx\b|experience|operations|support|transformation|"
    r"workforce|service delivery|customer service|client services|business process|outsourc|vendor|bpo|"
    r"partner success|customer success|consulting|operational excellence|quality", re.I)
TOO_JUNIOR = re.compile(r"team lead|team leader|supervisor|\bagent\b|associate|intern|specialist|coordinator", re.I)
# Other functions that slip through words like "operations" or "consulting".
OFF_TARGET = re.compile(
    r"engineer|engineering|developer|software|product manag|product director|security|devops|data scien|"
    r"machine learning|\bml\b|design|legal|counsel|accounting|accountant|tax|finance|treasury|payroll|"
    r"marketing|brand|content|recruit|talent|people partner|\bhr\b|account executive|sales|"
    r"business development|solutions? architect|it operations|network|cloud|infrastructure|platform|"
    r"clinical|medical|nurse|pharma|warehouse|fleet|logistics|supply chain|procurement|real estate", re.I)
LOCATION = re.compile(
    r"remote|emea|\buae\b|emirates|dubai|abu dhabi|saudi|riyadh|jeddah|canada|toronto|vancouver|montreal|"
    r"\busa?\b|united states|new york|san francisco|austin|chicago|boston|seattle|"
    r"\buk\b|united kingdom|london|manchester|ireland|dublin|netherlands|amsterdam|germany|berlin|munich|"
    r"portugal|lisbon|porto|spain|madrid|barcelona|poland|warsaw|krakow|wroclaw", re.I)
COUNTRY = {"ae": "United Arab Emirates", "sa": "Saudi Arabia", "ca": "Canada", "us": "United States",
           "gb": "United Kingdom", "ie": "Ireland", "nl": "Netherlands", "de": "Germany",
           "pt": "Portugal", "es": "Spain", "pl": "Poland"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read())
    time.sleep(DELAY)
    return data


def strip_html(text):
    text = html.unescape(text or "")                      # Greenhouse double-encodes
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|ul|ol)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def job(title, location, url, jid, date="", salary="", html_desc="", text_desc=""):
    return {"id": str(jid), "title": title or "", "location": location or "", "url": url, "date": date or "",
            "salary": salary, "html_desc": html_desc, "text_desc": text_desc, "fetch_desc": None}


# ---- one fetcher per ATS: returns a list of job dicts (via job()) -------------------------------

def fetch_greenhouse(slug):
    jobs = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")["jobs"]
    out = []
    for j in jobs:
        x = job(j["title"], (j.get("location") or {}).get("name"), j["absolute_url"], j["id"], j.get("updated_at"))
        x["fetch_desc"] = lambda s=slug, i=j["id"]: get_json(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs/{i}?pay_transparency=true")
        out.append(x)
    return out


def fill_greenhouse(x, d):
    x["html_desc"] = d.get("content", "")
    pay = d.get("pay_input_ranges") or []
    if pay:
        x["salary"] = "; ".join(f"{p.get('min_cents', 0) // 100}-{p.get('max_cents', 0) // 100} {p.get('currency_type', '')}" for p in pay)


def fetch_lever(slug):
    out = []
    for j in get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json"):
        cat = j.get("categories") or {}
        loc = ", ".join(filter(None, [cat.get("location")] + (cat.get("allLocations") or []))) or ""
        if j.get("workplaceType") == "remote":
            loc += " (remote)"
        date = datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat() if j.get("createdAt") else ""
        sr = j.get("salaryRange")
        salary = f"{sr.get('min')}-{sr.get('max')} {sr.get('currency')} {sr.get('interval', '')}".strip() if sr else ""
        out.append(job(j["text"], loc, j["hostedUrl"], j["id"], date, salary, text_desc=j.get("descriptionPlain", "")))
    return out


def fetch_ashby(slug):
    out = []
    for j in get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")["jobs"]:
        locs = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
        loc = ", ".join(filter(None, locs)) + (" (remote)" if j.get("isRemote") else "")
        comp = (j.get("compensation") or {}).get("compensationTierSummary", "")
        out.append(job(j["title"], loc, j["jobUrl"], j["id"], j.get("publishedAt"), comp,
                       html_desc=j.get("descriptionHtml", ""), text_desc=j.get("descriptionPlain", "")))
    return out


def fetch_smartrecruiters(slug):
    out, offset = [], 0
    while True:
        page = get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}")
        for j in page["content"]:
            l = j.get("location") or {}
            loc = l.get("fullLocation") or ", ".join(filter(None, [l.get("city"), COUNTRY.get(l.get("country"), l.get("country"))]))
            if l.get("remote"):
                loc += " (remote)"
            url = f"https://jobs.smartrecruiters.com/{(j.get('company') or {}).get('identifier', slug)}/{j['id']}"
            x = job(j["name"], loc, url, j["id"], j.get("releasedDate"))
            x["fetch_desc"] = lambda s=slug, i=j["id"]: get_json(f"https://api.smartrecruiters.com/v1/companies/{s}/postings/{i}")
            out.append(x)
        offset += 100
        if offset >= page.get("totalFound", 0) or not page["content"]:
            return out


def fill_smartrecruiters(x, d):
    secs = (d.get("jobAd") or {}).get("sections") or {}
    x["html_desc"] = "\n".join(s.get("text", "") for s in secs.values() if isinstance(s, dict))
    x["url"] = d.get("postingUrl") or x["url"]


def fetch_workable(slug):
    out = []
    for j in get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")["jobs"]:
        loc = ", ".join(filter(None, [j.get("city"), j.get("state"), j.get("country")]))
        if j.get("telecommuting"):
            loc += " (remote)"
        out.append(job(j["title"], loc, j.get("url") or j.get("shortlink"), j.get("shortcode"), j.get("published_on"),
                       html_desc=j.get("description", "")))
    return out


FETCHERS = {"greenhouse": (fetch_greenhouse, fill_greenhouse), "lever": (fetch_lever, None),
            "ashby": (fetch_ashby, None), "smartrecruiters": (fetch_smartrecruiters, fill_smartrecruiters),
            "workable": (fetch_workable, None)}


# ---- filtering ----------------------------------------------------------------------------------

def parse_date(s):
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def title_ok(t):
    return bool(SENIORITY.search(t) and FUNCTION.search(t)
                and not TOO_JUNIOR.search(t) and not OFF_TARGET.search(t))


def norm_url(u):
    return re.sub(r"[?#].*$", "", u.strip().lower().rstrip("/"))


def tracked_urls():
    path = HERE / "tracker.csv"
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {norm_url(r["url"]) for r in csv.DictReader(f) if r.get("url")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="directory for <slug>-<jobid>.json files")
    ap.add_argument("--limit-days", type=int, default=30, help="drop jobs with a date older than N days (default 30)")
    ap.add_argument("--employers", default=str(HERE / "employers.yaml"))
    args = ap.parse_args()

    import yaml
    groups = yaml.safe_load(open(args.employers, encoding="utf-8"))
    seen = tracked_urls()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.limit_days)
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    ok, failures, scanned, rows = 0, [], 0, []
    seen_roles = set()  # one row per company + title, even if posted in several cities
    for group, employers in groups.items():
        for e in employers:
            name, ats, slug = e["name"], e["ats"], e["slug"]
            try:
                fetch, fill = FETCHERS[ats]
                jobs = fetch(slug)
            except Exception as ex:
                failures.append(f"{name} ({ats}/{slug}): {ex}")
                continue
            ok += 1
            scanned += len(jobs)
            for x in jobs:
                if not title_ok(x["title"]) or not LOCATION.search(x["location"]):
                    continue
                d = parse_date(x["date"])
                if d and d < cutoff:
                    continue
                role = (name.lower(), x["title"].strip().lower())
                if norm_url(x["url"]) in seen or role in seen_roles:
                    continue
                seen_roles.add(role)
                try:  # full description, only for the few jobs that matched
                    if x["fetch_desc"]:
                        fill(x, x["fetch_desc"]())
                except Exception as ex:
                    failures.append(f"{name} job {x['id']} description: {ex}")
                text = x["text_desc"] or strip_html(x["html_desc"])
                rows.append((name, x["title"], x["location"], x["url"], x["date"][:10]))
                if out_dir:
                    rec = {"company": name, "title": x["title"], "location": x["location"], "url": x["url"],
                           "date": x["date"], "salary": x["salary"], "description_text": text}
                    (out_dir / f"{slug}-{x['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{'Company':<16} {'Date':<10} {'Title':<55} {'Location':<35} URL")
    for r in sorted(rows):
        print(f"{r[0][:16]:<16} {r[4]:<10} {r[1][:55]:<55} {r[2][:35]:<35} {r[3]}")
    print(f"\nEmployers OK: {ok}/{ok + len(failures)} | jobs scanned: {scanned} | matches: {len(rows)}")
    for f in failures:
        print("FAILED:", f, file=sys.stderr)


if __name__ == "__main__":
    main()
