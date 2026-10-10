# Per-job resume tailoring (ATS shortlist rules)

Every application gets its own resume, built from `profile/career.yaml` and checked against that job's description. No job is sent the master resume.

## 1. Read the job description
Save the full ad to `jobs/tailored/<id>/job_ad.txt`. Extract:
- Exact job title as written.
- Hard requirements (knockouts): years of experience, degree, certifications, languages, location, work authorization or visa, travel.
- Top 15–25 keywords and phrases, ranked by repetition and position (title, requirements list first).
- Tools and systems named (CRM, WFM, CCaaS, BI, AI tools).

## 2. Knockout check (before any writing)
For each hard requirement, mark met / not met / unclear, with the evidence from career.yaml.
- Any "not met" that the ad marks as required → do not shortlist. Log it in tracker `notes`.
- Visa or citizenship required and no sponsorship → do not shortlist.
- "Unclear" → shortlist, list it under `knockout_gaps` for Ahmed.

## 3. Tailor (facts never change)
Write `jobs/tailored/<id>/career.yaml`, a copy of the master with only these edits:
- **Headline:** lead with the job's exact title or nearest true equivalent, then 3–4 of the ad's top keywords that Ahmed has.
- **Summary:** rewrite 3–4 sentences to mirror the ad's language and priorities, using only facts in the master.
- **Bullet order:** per role, put bullets that match the ad's top keywords first.
- **Wording:** use the ad's exact terms where they describe the same thing (e.g. "customer satisfaction" → "CSAT"; "contact center" vs "call center"; "client partner" vs "account manager"). Use both the acronym and the long form once.
- **Skills:** reorder each group so ad keywords come first. Add a skill only if a bullet or certification in the master proves it.
- **Never:** add employers, titles, dates, metrics, degrees or certifications that are not in the master. Never use `needs_confirmation` items. No hidden or white text.

## 4. Build and gate
```
python3 resume/build_resume.py jobs/tailored/<id>/career.yaml jobs/tailored/<id>
python3 resume/ats_check.py --pdf jobs/tailored/<id>/Ahmed_Essam_Ali_Resume.pdf --yaml jobs/tailored/<id>/career.yaml jobs/tailored/<id>/job_ad.txt
```
Pass gates:
- Parse fidelity 100%.
- Keyword match ≥ 85% of the ad's terms (built-in list) and every term from step 1's top 10 present, unless it is a real gap.
- Exactly 2 pages.
If a gate fails, revise once. If it still fails, shortlist only if the fit score is ≥ 75, and record the missing terms as `ats_gaps`.

## 5. Cover letter
`jobs/tailored/<id>/cover_letter.txt`, 180–220 words. Name the company and title. Three proof points mapped to the ad's top three requirements. No generic claims.

## 6. Record
Tracker columns: `ats_match`, `ats_gaps`, `knockout_gaps`. Upload the tailored DOCX to ATS portals (better parse than PDF on Workday/Taleo); use the PDF for email.
