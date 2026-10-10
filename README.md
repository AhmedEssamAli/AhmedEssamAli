# Ahmed Essam Ali — resume and job pipeline

| Path | Purpose |
|---|---|
| `profile/career.yaml` | Single source of truth. Edit facts here only. |
| `resume/build_resume.py` | Builds ATS resume DOCX + PDF. `python3 resume/build_resume.py [yaml] [outdir]` |
| `resume/ats_check.py` | Parse-fidelity and keyword check. `python3 resume/ats_check.py [--pdf f --yaml f] [job_ad.txt ...]` |
| `resume/output/` | Master resume (DOCX, PDF). |
| `linkedin/profile.md` | LinkedIn text that matches the resume. |
| `jobs/criteria.yaml` | Roles, locations, scoring. |
| `jobs/tracker.csv` | Every job found, applied and its outcome. |
| `jobs/TAILORING.md` | Rules for per-job resume tailoring and ATS gates. |
| `jobs/tailored/<id>/` | Per-job ad, resume, cover letter. |
| `.claude/skills/apply-batch/` | Supervised apply in Ahmed's Chrome. |
