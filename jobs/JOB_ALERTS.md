# Job alerts setup (Ahmed, one time, ~30 minutes)

Why: Bayt and GulfTalent block bots, and LinkedIn, Indeed and Glassdoor need a login. Job-alert emails reach Gmail with no scraping. The weekly routine reads them from the Gmail label `Job Alerts`.

## 1. Gmail label and filter
1. Create label `Job Alerts`.
2. Create a filter: From contains `jobalerts-noreply@linkedin.com OR alert@indeed.com OR alert@indeedmail.com OR bayt.com OR gulftalent.com OR naukrigulf.com OR glassdoor.com` → Apply label `Job Alerts`, Never send to Spam. (Check the real sender of the first alert from each site and add it if it differs.)

## 2. Saved searches (daily alerts)
Use these titles, one alert each, per site. Seniority filter: Director / Senior / Manager. Date posted: last 24 hours.

| Site | Titles | Locations |
|---|---|---|
| LinkedIn | Director of Operations contact center; Head of Customer Experience; Client Services Director; CX Transformation; Contact Center Director | United Arab Emirates; Saudi Arabia; Canada; European Union; United Kingdom; Remote |
| Indeed | Contact Center Director; Head of Customer Experience; Client Services Director; Customer Operations Director | Remote; Toronto; Dubai (ae.indeed.com); London (uk.indeed.com) |
| Bayt | Customer Experience Manager; Contact Center Manager; Client Services Director | UAE; Saudi Arabia; Qatar |
| GulfTalent | Head of Contact Centre; Customer Service Director; Customer Experience | UAE; Saudi Arabia |
| Naukrigulf | Call Center Manager; Customer Experience Head | UAE; Saudi Arabia |

## 3. LinkedIn settings
- Open to Work: Recruiters only.
- Job alert frequency: Daily, email.

The routine marks alert jobs as `candidate`. Tailoring and the ATS gate run in `/apply-batch` on your PC, because only your browser can open those ads.
