#!/usr/bin/env python3
"""Discover senior ops / CX / transformation jobs (any vertical) from public, unauthenticated ATS JSON APIs.

Usage: python3 jobs/discover_api.py [--out DIR] [--limit-days 30]
Needs only the stdlib + PyYAML. Employers live in jobs/employers.yaml.
"""
import argparse, csv, html, json, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
TIMEOUT, WORKERS = 20, 8
HEADERS = {"User-Agent": "Mozilla/5.0 (job-discovery script)", "Accept": "application/json"}

SENIORITY = re.compile(r"\b(director|head|vp|vice president|senior manager|manager|lead|principal|consultant)\b", re.I)
FUNCTION = re.compile(
    r"customer|client|contact cent|call cent|\bcx\b|experience|operations|support|transformation|"
    r"workforce|service delivery|customer service|client services|business process|outsourc|vendor|bpo|"
    r"partner success|customer success|consulting|operational excellence|quality|"
    r"head of operations|operations director|shared services|\bgbs\b|business excellence|process excellence|"
    r"program manager|programme|strategy (?:&|and) operations|vendor management|customer care|"
    r"client relationship|relationship manager", re.I)
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
        return json.loads(r.read())


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


WD_TERMS = ["operations", "customer", "director"]
WD_CAP = 60  # max jobs pulled per search term (3 pages of 20)


def wd_date(s):
    """Workday postedOn is text like 'Posted Today' / 'Posted 5 Days Ago' / 'Posted 30+ Days Ago'."""
    s = (s or "").lower()
    now = datetime.now(timezone.utc)
    if "today" in s:
        return now.date().isoformat()
    if "yesterday" in s:
        return (now - timedelta(days=1)).date().isoformat()
    m = re.search(r"(\d+)\+?\s*days? ago", s)
    return (now - timedelta(days=int(m.group(1)))).date().isoformat() if m else ""


def fetch_workday(e):
    host, tenant, site = e["host"], e["tenant"], e["site"]
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    found = {}  # externalPath -> job, dedupes across search terms
    for term in WD_TERMS:
        for offset in range(0, WD_CAP, 20):
            body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term}).encode()
            req = urllib.request.Request(base + "/jobs", data=body, method="POST",
                                         headers={**HEADERS, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                page = json.loads(r.read())
            posts = page.get("jobPostings") or []
            for j in posts:
                path = j.get("externalPath")
                if path and path not in found:
                    x = job(j.get("title"), j.get("locationsText"), f"https://{host}/en-US/{site}{path}",
                            path.rsplit("_", 1)[-1], wd_date(j.get("postedOn")))
                    x["fetch_desc"] = lambda p=path: get_json(base + p)
                    found[path] = x
            if len(posts) < 20 or offset + 20 >= page.get("total", 0):
                break
    return list(found.values())


def fill_workday(x, d):
    info = d.get("jobPostingInfo") or {}
    x["html_desc"] = info.get("jobDescription", "")
    if info.get("startDate"):
        x["date"] = x["date"] or info["startDate"]


FETCHERS = {"greenhouse": (fetch_greenhouse, fill_greenhouse), "lever": (fetch_lever, None),
            "ashby": (fetch_ashby, None), "smartrecruiters": (fetch_smartrecruiters, fill_smartrecruiters),
            "workable": (fetch_workable, None),
            "workday": (fetch_workday, fill_workday)}


# ---- filtering ----------------------------------------------------------------------------------

def parse_date(s):
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


SENIOR_ONLY = re.compile(r"senior|director|head", re.I)


def title_ok(t):
    # "relationship manager" alone is too broad (retail banking): require a senior word
    if re.search(r"relationship manager", t, re.I) and not SENIOR_ONLY.search(t):
        return False
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


def process(e, cutoff, seen):
    """Fetch one employer, filter, then fetch descriptions of matches. Returns (n_scanned, matched jobs)."""
    ats = e["ats"]
    fetch, fill = FETCHERS[ats]
    jobs = fetch(e if ats == "workday" else (e.get("slug") or e["tenant"]))
    matched, seen_roles = [], set()  # one row per title, even if posted in several cities
    for x in jobs:
        if not title_ok(x["title"]) or not LOCATION.search(x["location"]):
            continue
        d = parse_date(x["date"])
        if d and d < cutoff:
            continue
        role = x["title"].strip().lower()
        if norm_url(x["url"]) in seen or role in seen_roles:
            continue
        seen_roles.add(role)
        matched.append(x)

    def describe(x):
        try:
            if x["fetch_desc"]:
                fill(x, x["fetch_desc"]())
        except Exception as ex:
            return f"job {x['id']} description: {ex}"

    if matched:
        with ThreadPoolExecutor(4) as pool:
            warnings = [w for w in pool.map(describe, matched) if w]
    else:
        warnings = []
    return len(jobs), matched, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="directory for <slug>-<jobid>.json files")
    ap.add_argument("--limit-days", type=int, default=30, help="drop jobs with a date older than N days (default 30)")
    ap.add_argument("--timeout-total", type=float, default=420, help="seconds to wait for all employers (default 420)")
    ap.add_argument("--employers", default=str(HERE / "employers.yaml"))
    args = ap.parse_args()

    import yaml
    groups = yaml.safe_load(open(args.employers, encoding="utf-8"))
    employers = [e for group in groups.values() for e in group]
    seen = tracked_urls()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.limit_days)
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    ok, failures, scanned, rows = 0, [], 0, []
    pool = ThreadPoolExecutor(WORKERS)
    futures = {pool.submit(process, e, cutoff, seen): e for e in employers}
    pending = set(futures)
    try:
        for f in as_completed(futures, timeout=args.timeout_total):
            pending.discard(f)
            e = futures[f]
            name = e["name"]
            try:
                n, matched, warnings = f.result()
            except Exception as ex:
                reason = str(ex) or type(ex).__name__
                failures.append(f"{name} ({e['ats']}): {reason}")
                print(f"ERR {name} {reason}", file=sys.stderr, flush=True)
                continue
            ok += 1
            scanned += n
            print(f"ok  {name} {n} jobs", file=sys.stderr, flush=True)
            failures.extend(f"{name} {w}" for w in warnings)
            slug = e.get("slug") or e["tenant"]
            for x in matched:
                text = x["text_desc"] or strip_html(x["html_desc"])
                rows.append((name, x["title"], x["location"], x["url"], x["date"][:10]))
                if out_dir:
                    rec = {"company": name, "title": x["title"], "location": x["location"], "url": x["url"],
                           "date": x["date"], "salary": x["salary"], "description_text": text}
                    (out_dir / f"{slug}-{x['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    except FutureTimeout:
        pass
    pool.shutdown(wait=False, cancel_futures=True)
    timed_out = [futures[f]["name"] for f in pending]
    for n in timed_out:
        print(f"ERR {n} timed out", file=sys.stderr, flush=True)

    print(f"{'Company':<16} {'Date':<10} {'Title':<55} {'Location':<35} URL")
    for r in sorted(rows):
        print(f"{r[0][:16]:<16} {r[4]:<10} {r[1][:55]:<55} {r[2][:35]:<35} {r[3]}")
    print(f"\nEmployers OK: {ok}/{len(employers)} | errors: {len(employers) - ok - len(timed_out)} | "
          f"timed out: {len(timed_out)} | jobs scanned: {scanned} | matches: {len(rows)}")
    for f in failures:
        print("FAILED:", f, file=sys.stderr)
    if timed_out:
        print("TIMED OUT:", ", ".join(timed_out), file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # worker threads may still be blocked on slow requests; do not wait for them


if __name__ == "__main__":
    main()
