"""Convert Ahmed's net monthly salary floors to gross annual floors per country.

Run: python3 jobs/salary_floor.py   -> writes jobs/salary_floor.yaml

Floors (set by Ahmed): EUR 4,000 net/month for EU and UK; USD 5,000 net/month
for the Gulf, US, Canada and remote; EGP 240,000 net/month for Egypt.
Tax rates are ESTIMATES: effective rate (income tax + employee social charges)
for a single filer at this income, no expat regimes (no NL 30% ruling, no PT IFICI).
FX comes from open.er-api.com at run time.
"""
import json
import urllib.request
from datetime import date
from pathlib import Path

import yaml

FLOORS = {"EUR": 4000, "USD": 5000, "EGP": 240000}  # net per month, in floor currency

# country: (local currency, floor currency, effective tax rate estimate, note)
COUNTRIES = {
    "United Arab Emirates": ("AED", "USD", 0.00, "no personal income tax"),
    "Saudi Arabia": ("SAR", "USD", 0.00, "no personal income tax for expats; GOSI not charged on expat pay"),
    "Qatar": ("QAR", "USD", 0.00, "no personal income tax"),
    "United States": ("USD", "USD", 0.27, "federal + FICA + average state"),
    "Canada": ("CAD", "USD", 0.27, "Ontario, federal + provincial + CPP/EI"),
    "United Kingdom": ("GBP", "EUR", 0.23, "income tax + NI, England"),
    "Ireland": ("EUR", "EUR", 0.32, "income tax + USC + PRSI"),
    "Netherlands": ("EUR", "EUR", 0.33, "box 1, no 30% ruling"),
    "Germany": ("EUR", "EUR", 0.41, "tax class I + social insurance"),
    "Spain": ("EUR", "EUR", 0.30, "IRPF + social security, Madrid"),
    "Portugal": ("EUR", "EUR", 0.36, "IRS + social security, no IFICI regime"),
    "Poland": ("PLN", "EUR", 0.30, "employment contract (UoP), PIT + ZUS"),
    "Egypt": ("EGP", "EGP", 0.26, "income tax top bracket + capped social insurance"),
    "Remote": ("USD", "USD", 0.26, "assumes Ahmed stays tax-resident in Egypt"),
}


def usd_rates():
    with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=20) as r:
        d = json.load(r)
    return d["rates"], d.get("time_last_update_utc", str(date.today()))


def main():
    rates, fx_date = usd_rates()
    rows = {}
    for country, (cur, floor_cur, tax, note) in COUNTRIES.items():
        fx = rates[cur] / rates[floor_cur]  # local currency per 1 unit of floor currency
        net_month = FLOORS[floor_cur] * fx
        gross_year = net_month * 12 / (1 - tax)
        rows[country] = {
            "currency": cur,
            "net_month_floor": round(net_month, -1),
            "gross_year_floor": round(gross_year, -3),
            "gross_month_floor": round(gross_year / 12, -1),
            "based_on": f"{FLOORS[floor_cur]:,} {floor_cur} net/month",
            "tax_rate_assumed": tax,
            "tax_note": f"ESTIMATE: {note}",
        }
    out = {
        "generated": str(date.today()),
        "fx_source": f"open.er-api.com, {fx_date}",
        "rule": "Compare posted or estimated GROSS annual pay with gross_year_floor for the job's country. "
                "Below floor = flag, not drop. Remote and unknown countries use the Remote row.",
        "countries": rows,
    }
    path = Path(__file__).with_name("salary_floor.yaml")
    path.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")
    for c, r in rows.items():
        print(f"{c:<22} {r['currency']}  net/mo {r['net_month_floor']:>12,.0f}  gross/yr {r['gross_year_floor']:>12,.0f}  tax {r['tax_rate_assumed']:.0%}")


if __name__ == "__main__":
    main()
