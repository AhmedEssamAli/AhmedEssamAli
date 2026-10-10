#!/usr/bin/env python3
"""ATS parse check for the resume PDF, plus keyword match against job ads.

Usage (from repo root):
    python3 resume/ats_check.py [job_ad.txt ...]

Exit code 1 if any parse check fails. Job-ad matching is informational.
"""
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "resume" / "output" / "Ahmed_Essam_Ali_Resume.pdf"
CAREER = ROOT / "profile" / "career.yaml"

HEADINGS = ["SUMMARY", "EXPERIENCE", "EDUCATION", "CERTIFICATIONS", "SKILLS", "LANGUAGES"]
ALLOWED_NON_ASCII = {"•", "–"}  # bullet, en dash

STOPWORDS = set("""
a about above across after again against all also am an and any are as at be because been
before being below between both but by can could did do does doing down during each etc few for
from further had has have having he her here hers herself him himself his how i if in into is it
its itself just me more most my myself no nor not now of off on once only or other our ours
ourselves out over own per same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very via was we were
what when where which while who whom why will with within would you your yours yourself yourselves
""".split())

# Canonical CX / BPO / operations / leadership terms -> accepted surface forms.
TERMS = {
    "contact center": ["contact centre", "call center", "call centre"],
    "bpo": ["business process outsourcing"],
    "outsourcing": [],
    "customer experience": [],
    "cx": [],
    "customer service": [],
    "customer satisfaction": [],
    "csat": [],
    "nps": ["net promoter score"],
    "omnichannel": ["omni channel"],
    "self service": [],
    "client relationship": [],
    "client services": [],
    "client escalation": [],
    "account management": ["account manager"],
    "stakeholder management": ["stakeholder engagement"],
    "vendor management": ["supplier management"],
    "executive business review": [],
    "qbr": ["quarterly business review"],
    "p&l": ["pnl"],
    "budget": ["budgeting"],
    "forecasting": ["forecast"],
    "capacity planning": [],
    "workforce management": [],
    "wfm": [],
    "sla": ["service level agreement"],
    "kpi": ["key performance indicator"],
    "operations": ["operational"],
    "operational excellence": [],
    "quality": [],
    "quality assurance": ["qa"],
    "copc": [],
    "six sigma": ["6 sigma"],
    "lean six sigma": [],
    "process improvement": [],
    "continuous improvement": [],
    "change management": [],
    "digital transformation": [],
    "transformation": [],
    "automation": [],
    "ai": [],
    "generative ai": ["genai", "gen ai"],
    "machine learning": ["ml"],
    "chatbot": ["virtual agent"],
    "power bi": ["powerbi"],
    "sql": [],
    "python": [],
    "excel": ["microsoft excel"],
    "dashboard": [],
    "analytics": [],
    "data analysis": [],
    "reporting": [],
    "attrition": ["turnover"],
    "retention": [],
    "employee engagement": [],
    "coaching": ["coach"],
    "training": [],
    "recruitment": ["hiring"],
    "leadership": [],
    "team leadership": [],
    "people management": [],
    "talent": [],
    "root cause analysis": ["rca"],
    "risk management": [],
    "compliance": [],
    "regulatory compliance": [],
    "contract negotiation": [],
    "revenue": [],
    "gross margin": [],
    "cost reduction": ["cost savings"],
    "business development": [],
    "program launch": ["go live"],
    "first contact resolution": ["fcr"],
    "average handle time": ["aht"],
    "crm": ["customer relationship management"],
    "consulting": [],
    "governance": [],
    "service delivery": [],
    "headcount": [],
    "knowledge management": [],
    "speed to proficiency": [],
}

TOKEN_RE = re.compile(r"[a-z0-9]+(?:&[a-z0-9]+)*")


def lemma(tok):
    """Crude plural stripping, applied identically to ads and resume."""
    if len(tok) > 2 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def raw_tokens(text):
    return TOKEN_RE.findall(text.lower())


def lemmas(text):
    return [lemma(t) for t in raw_tokens(text)]


FORMS = {}      # canonical -> list of token tuples
FORM_TO_TERM = {}  # token tuple -> canonical
for canon, aliases in TERMS.items():
    forms = [tuple(lemmas(f)) for f in [canon] + aliases]
    FORMS[canon] = forms
    for f in forms:
        FORM_TO_TERM[f] = canon


def contains(seq, sub):
    n = len(sub)
    return any(tuple(seq[i:i + n]) == sub for i in range(len(seq) - n + 1))


def ad_keywords(text):
    """Unigrams and bigrams without stopwords, kept only if in the built-in term list."""
    raw = raw_tokens(text)
    lem = [lemma(t) for t in raw]
    found = set()
    for i in range(len(raw)):
        if raw[i] not in STOPWORDS:
            cand = (lem[i],)
            if cand in FORM_TO_TERM:
                found.add(FORM_TO_TERM[cand])
        if i + 1 < len(raw) and raw[i] not in STOPWORDS and raw[i + 1] not in STOPWORDS:
            cand = (lem[i], lem[i + 1])
            if cand in FORM_TO_TERM:
                found.add(FORM_TO_TERM[cand])
    return found


def run_pdftotext(pdf):
    result = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                            capture_output=True, text=True, check=True)
    return result.stdout


def norm(s):
    return " ".join(str(s).split()).casefold()


def starts_line(line, s):
    core = re.sub(r"^[^\w]+", "", line.strip())  # drop bullet glyphs
    return norm(core).startswith(norm(s))


def confirm_probes(item):
    probes = [item]
    head = item.split(":")[0]
    if len(head.split()) >= 3:
        probes.append(head)
    probes += [q for q in re.findall(r"'([^']{3,})'", item)]
    return probes


results = []


def check(label, ok, detail=""):
    results.append(ok)
    status = "PASS" if ok else "FAIL"
    print(f"{status}  {label}" + (f"  [{detail}]" if detail else ""))


def resume_checks():
    cv = yaml.safe_load(CAREER.read_text(encoding="utf-8"))
    text = run_pdftotext(PDF)
    flat = norm(text)
    digits = re.sub(r"\D", "", text)
    lines = text.splitlines()

    print("== Resume parse checks ==")
    contact = cv["contact"]
    check("name", norm(cv["name"]) in flat, cv["name"])
    check("email", norm(contact["email"]) in flat, contact["email"])
    phone_digits = re.sub(r"\D", "", contact["phone"])
    check("phone digits", phone_digits in digits, contact["phone"])
    check("linkedin URL", norm(contact["linkedin"]) in flat, contact["linkedin"])

    heading_line = {}
    pos = 0
    for h in HEADINGS:
        idx = next((i for i in range(pos, len(lines))
                    if lines[i].strip().casefold() == h.casefold()), None)
        check(f"heading {h} (in order)", idx is not None,
              f"line {idx + 1}" if idx is not None else "not found after previous heading")
        if idx is not None:
            heading_line[h] = idx
            pos = idx + 1

    exp = cv["experience"]
    exp_start = heading_line.get("EXPERIENCE", 0)
    exp_end = heading_line.get("EDUCATION", len(lines))
    title_idx = []
    cursor = exp_start + 1
    for e in exp:
        idx = next((i for i in range(cursor, exp_end) if starts_line(lines[i], e["title"])), None)
        check(f"experience title: {e['title']}", idx is not None,
              f"line {idx + 1}" if idx is not None else "not found in EXPERIENCE")
        title_idx.append(idx)
        if idx is not None:
            cursor = idx + 1
    for e, idx in zip(exp, title_idx):
        if idx is None:
            check(f"experience start date: {e['title']} ({e['start']})", False, "title not found")
            check(f"experience end date: {e['title']} ({e['end']})", False, "title not found")
            continue
        header = lines[idx]
        for key in ("start", "end"):
            v = str(e[key])
            pat = r"(?<!\w)" + re.escape(v) + r"(?!\w)"
            check(f"experience {key} date: {e['title']} ({v})",
                  re.search(pat, header, re.IGNORECASE) is not None,
                  "header line" if re.search(pat, header, re.IGNORECASE) else "not on title line")
    found = [i for i in title_idx if i is not None]
    in_order = found == sorted(found) and len(found) == len(exp)
    check("experience entries in YAML order", in_order)

    for e in cv["education"]:
        check(f"education degree: {e['degree']}", norm(e["degree"]) in flat, e["degree"])
    for c in cv["certifications"]:
        check(f"certification: {c['name']}", norm(c["name"]) in flat, c["name"])

    for item in cv.get("needs_confirmation", []) or []:
        hits = [p for p in confirm_probes(item) if norm(p) in flat]
        label = "needs_confirmation text absent: " + item.split(":")[0][:60]
        check(label, not hits, f"matched: {hits[0]}" if hits else "")

    odd = Counter()
    where = {}
    for ln, line in enumerate(lines, 1):
        for ch in line:
            if ord(ch) > 127 and ch not in ALLOWED_NON_ASCII:
                odd[ch] += 1
                where.setdefault(ch, ln)
    if odd:
        parts = []
        for ch, n in odd.items():
            cat = unicodedata.category(ch)
            kind = "private-use" if cat == "Co" else unicodedata.name(ch, "unnamed")
            parts.append(f"U+{ord(ch):04X} {kind} x{n} (first line {where[ch]})")
        check("non-ASCII glyphs (only bullet and en dash allowed)", False, "; ".join(parts))
    else:
        check("non-ASCII glyphs (only bullet and en dash allowed)", True)

    passed = sum(results)
    total = len(results)
    print(f"\nParse fidelity: {passed}/{total} = {100 * passed / total:.1f}%")
    return text


def job_ad_checks(paths, resume_text):
    resume_tok = tuple(lemmas(resume_text))
    print("\n== Job ad keyword match ==")
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="replace")
        kws = ad_keywords(text)
        matched = sorted(k for k in kws if any(contains(resume_tok, f) for f in FORMS[k]))
        missing = sorted(k for k in kws if k not in matched)
        print(f"\n-- {p} --")
        if not kws:
            print("No built-in terms found in this ad.")
            continue
        print(f"Ad terms: {len(kws)}")
        print(f"Matched ({len(matched)}): {', '.join(matched) or '-'}")
        print(f"Missing ({len(missing)}): {', '.join(missing) or '-'}")
        print(f"Match: {100 * len(matched) / len(kws):.1f}%")


def main():
    resume_text = resume_checks()
    if len(sys.argv) > 1:
        job_ad_checks(sys.argv[1:], resume_text)
    sys.exit(1 if not all(results) else 0)


if __name__ == "__main__":
    main()
