---
name: apply-batch
description: Supervised job applications for Ahmed. Use when Ahmed says "apply batch", "apply to this week's jobs" or "/apply-batch". Opens each shortlisted job in Ahmed's signed-in Chrome (Claude in Chrome), fills the form from profile/career.yaml and the tailored resume, and stops before Submit so Ahmed clicks it.
---

# Apply batch (supervised)

Runs on Ahmed's computer in Claude desktop with Claude in Chrome. Never in an unattended cloud session: LinkedIn and Indeed forbid automated applying, and the account is Ahmed's.

## Inputs
- `jobs/tracker.csv` rows with `status = shortlisted`, highest `fit_score` first.
- `jobs/tailored/<id>/resume.pdf` and `cover_letter.txt` for each row.
- `profile/career.yaml` for every answer. Never invent a fact.

## Steps
1. `git pull`. Read the tracker. Show Ahmed the batch (max 15 per day): title, company, location, fit score, salary estimate. Ask which to skip.
2. Load the chrome-browser skill. Open each job URL in a new tab in Ahmed's Chrome.
3. Prefer LinkedIn Easy Apply or Indeed Apply. For external ATS (Workday, Greenhouse, Lever, SuccessFactors), fill only if Ahmed is already signed in; never create accounts or passwords.
4. Fill contact, experience and education fields from `career.yaml`. Upload the tailored resume. Paste the cover letter where asked.
5. Stop and ask Ahmed, never guess, on: salary expectation, visa or sponsorship, notice period, start date, relocation terms, legal declarations, diversity questions, references, any test or assessment.
6. Stop before the final Submit. Ahmed reviews and clicks Submit himself.
7. After each submit, update the row: `status = applied`, `applied_date`, `notes`. After the batch, commit `jobs/tracker.csv` and push.

## Rules
- Pace: wait 1–3 minutes between applications. Max 15 per day.
- Skip Teleperformance/TP postings.
- If a site shows a CAPTCHA, a bot warning or an account-restriction notice, stop the batch and tell Ahmed.
