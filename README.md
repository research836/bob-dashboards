# Bailing Out Benji dashboard data

This project keeps the six research dashboards on bailingoutbenji.com up to date automatically.

Every Monday morning, GitHub runs `build_dashboards.py`. It reads the Benji Directory and Online Breeder Case Builder Airtable bases, calculates the totals each dashboard shows, and saves them in `docs/data/`. GitHub Pages publishes that folder at:

`https://research836.github.io/bob-dashboards/data/`

Each dashboard on the website reads its file every time a visitor opens the page, so Airtable edits show up after the next run with nothing to re-paste.

**Only totals are published.** No names, addresses, phone numbers, or record IDs ever leave Airtable.

| Dashboard | Website page | Data file |
|---|---|---|
| Licensee analysis | (not yet published) | `licensee.json` |
| Online sellers | Online Puppy Seller Research | `online-sellers.json` |
| Pet store sourcing | Where Do Pet Store Puppies Come From? | `pet-store-sourcing.json` |
| Breeders | Breeder Research | `breeders.json` |
| Brokers | Broker Research | `brokers.json` |
| USDA Annual Audit | USDA Violations | `usda.json` |

---

## Updating the dashboards right away

1. Open the repository on GitHub and click the **Actions** tab.
2. Click **Update dashboard data** in the left list.
3. Click **Run workflow**, then the green **Run workflow** button.
4. Wait for the green check mark (usually a few minutes).
5. Clear the WP Rocket cache. GitHub can also take up to 10 minutes to publish the new files.

To check what is live, open `https://research836.github.io/bob-dashboards/`. It shows the date of the last update.

---

## If a run fails (red X)

Click the failed run, then **build** to see the message. The most common ones:

- **"AIRTABLE_TOKEN is not set"**: the secret is missing. Add it under Settings > Secrets and variables > Actions, named exactly `AIRTABLE_TOKEN`.
- **"Airtable error 401" or "403"**: the token expired or lost access to a base. Create a new read-only token (scopes `data.records:read` and `schema.bases:read`, both bases) and replace the secret.
- **"STOPPED: ... dropped from X to Y"**: a safety check. If a headline total drops by more than 40% from the last update, nothing is published, so a broken view or a bulk edit in progress can't put wrong numbers on the website. Check Airtable. If the drop is real, open `build_dashboards.py`, change `MAX_DROP = 0.40` to a higher number, run once, and change it back.

A failed run never breaks the website. The dashboards keep showing the last good numbers.

---

## Things to update by hand

**USDA year write-ups.** `static/usda_narratives.json` holds the headline and paragraph for each completed year. The current year writes its own "Year in progress" text. When a year ends, add an entry for it (copy the format of the others) or the dashboard uses a simple automatic sentence.

**GoodDog numbers.** The "Audit in progress" section uses `static/gooddog_summary.json`, a snapshot of the GoodDog audit spreadsheet. It stays fixed until the GoodDog data moves into the Case Builder base, then the script can read it directly.

**New year columns in Airtable (once a year).** The script reads the yearly link fields (for example "2026 Pet Store Connections") by their field IDs. When 2027 columns are added in Airtable, their IDs need to be added near the top of `build_dashboards.py` (`BR_PS`, `BR_ON`, `BK_PS`, `BK_ON`, `PS_SUP`, `WS_SUP`).

**Renaming fields or options is safe.** The script uses field IDs, so renaming a field doesn't break anything. Renaming a License Type option (like "USDA Breeder") or a pet store Status option ("Open") does, since those names are matched in the script.

---

## What each dashboard counts

- **Licensee:** all breeders and brokers with a mapped license status and a state, including those who also or only sell cats. "USDA license ended" means cancelled, suspended, or revoked; the year comes from the former license number.
- **Breeders and brokers:** only those currently active: active USDA or state license, no license found but documented selling, and former licensees documented selling to pet stores or online in the last three years.
- **Pet store sourcing:** stores with Status = Open and their breeder and broker connections from the last three years of pet store connection columns.
- **Online sellers:** websites with at least 250 documented sellers.
- **USDA Annual Audit:** Class A and Class B inspections from 2021 on. The current year is marked "In Progress."
- **USDA violations** everywhere use USDA inspections only, past five years, through the "All NCIs (Last 5 Years)" fields.

---

## Files

- `build_dashboards.py`: the script.
- `.github/workflows/update-dashboards.yml`: the Monday schedule and the Run workflow button.
- `static/`: the GoodDog snapshot and USDA write-ups.
- `docs/data/`: the published totals (written by the script; don't edit by hand).
- `dashboards/`: the dashboard pages themselves, for reference. The embed codes pasted into WordPress are made from these.
