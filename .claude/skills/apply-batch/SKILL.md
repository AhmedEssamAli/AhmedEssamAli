---
name: apply-batch
description: Supervised job applications for Ahmed. Use when Ahmed says "apply batch", "apply to this week's jobs" or "/apply-batch". Opens each shortlisted job in Ahmed's signed-in Chrome (Claude in Chrome), fills the form from profile/career.yaml and the tailored resume, and stops before Submit so Ahmed clicks it.
---

# Apply batch (supervised)

Runs on Ahmed's computer in Claude desktop with Claude in Chrome. Never in an unattended cloud session: LinkedIn and Indeed forbid automated applying, and the account is Ahmed's.

## Setup (once, on Ahmed's PC)
- Clone the repo and check out `claude/trusting-ptolemy-vnwcuc`.
- Python 3 with `pip install python-docx pyyaml pypdf`. LibreOffice is optional (PDF only; the DOCX is what ATS portals get).

## Inputs
- `jobs/tracker.csv` rows with `status = shortlisted` (cloud already tailored) or `status = candidate` (from job-alert emails; tailor here), highest `fit_score` first.
- `jobs/TAILORING.md`: the tailoring rules and ATS gate.
- `jobs/tailored/<id>/`: tailored resume DOCX/PDF and `cover_letter.txt`. Never upload the master resume.
- `profile/career.yaml` for every answer. Never invent a fact.

## Steps
1. `git pull`. Read the tracker. Show Ahmed the batch (max 15 per day): title, company, location, fit score, salary estimate. Ask which to skip.
2. Load the chrome-browser skill. Open each job URL in a new tab in Ahmed's Chrome.
3. For a `candidate` row (no `jobs/tailored/<id>/` yet): read the full ad from the open page, save it to `jobs/tailored/<id>/job_ad.txt`, run the knockout check, and skip the job if a required item fails. Otherwise tailor per `jobs/TAILORING.md`, build with `python resume/build_resume.py jobs/tailored/<id>/career.yaml jobs/tailored/<id>`, run the ATS gate with `python resume/ats_check.py --pdf ... --yaml ... jobs/tailored/<id>/job_ad.txt` (if no PDF was built, skip the gate and say so), write the cover letter, and fill `ats_match`, `ats_gaps`, `knockout_gaps` in the tracker. Show Ahmed the ATS match before applying.
4. Prefer LinkedIn Easy Apply or Indeed Apply. For external ATS (Workday, Greenhouse, Lever, SuccessFactors), fill only if Ahmed is already signed in; never create accounts or passwords.
5. Fill contact, experience and education fields from `career.yaml`. Upload the tailored resume. Paste the cover letter where asked.
6. Stop and ask Ahmed, never guess, on: salary expectation, visa or sponsorship, notice period, start date, relocation terms, legal declarations, diversity questions, references, any test or assessment.
7. Stop before the final Submit. Ahmed reviews and clicks Submit himself.
8. After each submit, update the row: `status = applied`, `applied_date`, `notes`. After the batch, commit `jobs/tracker.csv` and push.

## Rules
- Pace: wait 1–3 minutes between applications. Max 15 per day.
- Skip Teleperformance/TP postings.
- If a site shows a CAPTCHA, a bot warning or an account-restriction notice, stop the batch and tell Ahmed.
