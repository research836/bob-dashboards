"""
Bailing Out Benji: dashboard data builder
-----------------------------------------
Reads the Benji Directory and Online Breeder Case Builder Airtable bases,
calculates the totals shown on the website dashboards, and writes one JSON
file per dashboard to docs/data/. GitHub Pages publishes that folder, and
each dashboard on bailingoutbenji.com reads its file when a visitor opens it.

Only totals are written. No names, addresses, phone numbers, or record IDs
ever leave Airtable.

Runs automatically from .github/workflows/update-dashboards.yml.
Needs one secret: AIRTABLE_TOKEN (a read-only Airtable personal access token).
"""

import collections
import datetime as dt
import json
import os
import re
import statistics
import sys
import time

import requests

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
BASE = "appQXaAEVkvVDOFCZ"          # Benji Directory
CASE_BASE = "appRqYOIqxJ2lc46O"     # Online Breeder Case Builder
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Safety check: if any headline total drops by more than this share compared
# with the last published data, the run stops and nothing is published.
# This protects the website from a bad Airtable export or a broken view.
MAX_DROP = 0.40

T_BREEDERS = "tblEUKeoTEVMc1OMq"
T_BROKERS = "tblh3HL6vlHV74J9Q"
T_STORES = "tblaLPUmriGe8uB0e"
T_SITES = "tblXG9dzSDHZUcF5z"
T_INSPECTIONS = "tblx3M0FXNWBIaJjW"
T_CASES = "tbldYw9iI27OhnN0q"

# Field IDs (IDs never change when a field is renamed in Airtable).
BR = dict(state="fldAQjmVwobN2LIKb", lt="fldRnTOHb7MqdlR5P", sl="fldEIRlcd3fVEhWek",
          former="fld0XggcA7X4p19Ml", adults="fldj3p9l3Et0diQDo", breeds="fldhKkSAxTAUHFcpd",
          ps="fldO2J3fQtusW0uBc", online="fldIan1Z9Ha4fNGNM", web="fldD7blVFZyh37SGd",
          tobroker="fldiRljtpEN8k3X5c", nci="fldWN43D7y4HCJoF1", serious="fldzOLxSQjhQqHyHa",
          insp="fldATjc5UCxH9kyui")
BR_PS = {2026: "fldVPBmKzgGFgkmUD", 2025: "fld2y1VLV2RaMLVXN", 2024: "fldSsQQcIbSv3vEJa",
         2023: "fldzJvd1aJ86jH21c", 2022: "fldQFlFLUNVJydOLC", 2021: "fld7r34aJT4U7Ske8"}
BR_ON = {2026: "fldbajGWMLOW7zlGY", 2025: "fldxt11IvWMOsOPpp", 2024: "fldCvildNWGRjTHXe",
         2023: "fldYaAR1r9tUqqwiF", 2022: "fldHyxdwDilJQks26"}

BK = dict(state="flddZgTD85XWXOD7B", lt="flduwQlpNOyz8oMsf", sl="fldhROSUPK14zkRBK",
          former="fldD6dNUcOJdk449L", ps="fldcuISYBScX3Beem", nci="fldSOJbUUogSfyva1",
          serious="fld40fH1fZpv1mUjO", insp="fldexBfSoxYoEeyqY")
BK_PS = {2026: "fldOeP6QK9xBKZZjc", 2025: "fldaQhcLuYaGljxrr", 2024: "fldvBNnUkSEEYyz6A",
         2023: "fldcSsKJMqUfeKXoC", 2022: "fldtOictwuHStgJ82", 2021: "flds2Xtk2nNjfEV4q"}
BK_ON = {2026: "fldvBYHiafBXF3MM1", 2025: "fldaCYyq7DyXnRKMP", 2024: "fldGKUOFPDc1KGCnT",
         2023: "fldTgbtxwWewuCem4", 2022: "fldVN61BsrgExy2nQ"}

PS = dict(state="fldheQR1HPUmAWUKH", status="fldPuZEX5R419iw2Y")
PS_SUP = {2026: ("fldmfG7eFp67afL4U", "fldGR9ZMQwfz02qL8"),
          2025: ("fld2grqF7n63EXrLx", "fldtTyd8RXM6ndAQj"),
          2024: ("fldI3iukUf7RLtIBL", "fldlcf12wWT0GwDYb")}

WS = dict(name="fldnFCeXXZg8tfHPY", type="fldmyfvtvByt7bG4r")
WS_SUP = {2026: ("fldcpV1qDcmTS3uo9", "fldUvg4L7TYMmbXjz"),
          2025: ("fld1qUYbNB1YCu7NX", "fldEzRvTpiN7xx2an"),
          2024: ("fldfliiDKCaNSeePk", "fldHxh6QrZLpPlL5F"),
          2023: ("fldh3RE9CPkpRJ0vq", "fld9XFMKpZQCM8gcY"),
          2022: ("fldFffYAETr4SDe2T", "fldcb1zSQ95cuIxnt")}

IN = dict(date="fldVX7YyI3jBlcYd3", cls="flddMAJ9dMFPV9EAR", source="fld1A4oBY3EhzaxjT",
          direct="fldLJPuugbsmBxY2t", critical="fldqoIruEd23P0B7a", noncrit="fldqOpHBZDFnWET6O",
          state="fld37juyYzBLA10Cx", cats="fldZwyWJDuSbtKr46", sev="fldGaMYd0BcIyuENW")

CB = dict(state="fldJTCp6N0uMLiFhZ", markets="fldjUWGT28x1k4u2N", xplat="fldJ4AOMBgDvoJsxz")

US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
             "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
             "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
             "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
             "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
             "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
             "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
             "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
             "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
             "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
             "DC": "District of Columbia"}

TODAY = dt.date.today()
THIS_YEAR = TODAY.year
RECENT_YEARS = {THIS_YEAR - 2, THIS_YEAR - 1, THIS_YEAR}   # "documented selling recently"


# ----------------------------------------------------------------------------
# Airtable reading
# ----------------------------------------------------------------------------
def fetch(base, table, fields):
    """Return every record as {"id": ..., "f": {fieldId: value}}."""
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        sys.exit("AIRTABLE_TOKEN is not set. Add it under Settings > Secrets and variables > Actions.")
    url = f"https://api.airtable.com/v0/{base}/{table}"
    params = [("pageSize", "100"), ("returnFieldsByFieldId", "true")] + [("fields[]", f) for f in fields]
    out, offset = [], None
    while True:
        p = params + ([("offset", offset)] if offset else [])
        for attempt in range(5):
            r = requests.get(url, params=p, headers={"Authorization": f"Bearer {token}"}, timeout=60)
            if r.status_code == 429:
                time.sleep(30)
                continue
            break
        if r.status_code != 200:
            sys.exit(f"Airtable error {r.status_code} reading {table}: {r.text[:300]}")
        data = r.json()
        out += [{"id": x["id"], "f": x.get("fields", {})} for x in data["records"]]
        offset = data.get("offset")
        if not offset:
            return out
        time.sleep(0.22)   # stay under Airtable's 5 requests per second


def sel(v):
    """Single select / text value as plain text."""
    if isinstance(v, dict):
        return v.get("name")
    return v


def multi(v):
    return [sel(x) for x in (v or [])]


def links(v):
    return [x["id"] if isinstance(x, dict) else x for x in (v or [])]


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def fields_of(*dicts):
    out = []
    for d in dicts:
        out += list(d.values()) if isinstance(d, dict) else list(d)
    flat = []
    for f in out:
        flat += list(f) if isinstance(f, tuple) else [f]
    return sorted(set(flat))


# ----------------------------------------------------------------------------
# License categories
# ----------------------------------------------------------------------------
ACTIVE = {"USDA Breeder", "USDA Broker", "Re-Licensed as Broker"}
CUSDA = {"Suspended / Revoked", "USDA License Revoked", "USDA Suspended"}
CSTATE = {"Cancelled State License", "Cancelled State", "State License Revoked"}
UNLIC = {"Unlicensed- Active Seller", "Unlicensed Broker"}


def license_cat(lt):
    """Public categories used on the licensee, breeder, and broker dashboards."""
    if lt in ACTIVE:
        return "active"
    if lt and (lt.startswith("Cancelled USDA") or lt in CUSDA):
        return "cusda"
    if lt == "State Licensed":
        return "state"
    if lt in CSTATE:
        return "cstate"
    if lt in UNLIC:
        return "unlic"
    return None


def seller_cat(lt):
    """Wider grouping for suppliers and online sellers (anyone documented selling)."""
    c = license_cat(lt)
    if c:
        return c
    if lt == "USDA License Expired":
        return "cusda"
    if lt == "Unlicensed - No longer selling":
        return "unlic"
    return "other"


def is_cat(sl, breeds):
    return "cat" in (sl or "").lower() or any((b or "").lower().startswith("cat") for b in breeds)


USDA_NO = re.compile(r"\b\d{2}\s*-\s*[AB]\s*-\s*\d+")
YEAR = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")


def cancel_year(text):
    years = []
    for line in (text or "").split("\n"):
        if USDA_NO.search(line):
            years += [int(y) for y in YEAR.findall(line)]
    return max(years) if years else None


# ----------------------------------------------------------------------------
# Load everything
# ----------------------------------------------------------------------------
def load():
    print("Reading Airtable...")
    breeders = fetch(BASE, T_BREEDERS, fields_of(BR, BR_PS, BR_ON))
    brokers = fetch(BASE, T_BROKERS, fields_of(BK, BK_PS, BK_ON))
    stores = fetch(BASE, T_STORES, fields_of(PS, PS_SUP))
    sites = fetch(BASE, T_SITES, fields_of(WS, WS_SUP))
    insp = fetch(BASE, T_INSPECTIONS, fields_of(IN))
    cases = fetch(CASE_BASE, T_CASES, fields_of(CB))
    print(f"  {len(breeders)} breeders, {len(brokers)} brokers, {len(stores)} pet stores, "
          f"{len(sites)} websites, {len(insp)} inspections, {len(cases)} case builder profiles")
    return breeders, brokers, stores, sites, insp, cases


def people(breeders, brokers):
    """One normalized row per breeder and broker."""
    rows = {}
    for kind, recs, F, PSY, ONY in (("breeder", breeders, BR, BR_PS, BR_ON), ("broker", brokers, BK, BK_PS, BK_ON)):
        for r in recs:
            f = r["f"]
            lt = sel(f.get(F["lt"]))
            sl = sel(f.get(F["sl"])) or ""
            breeds = multi(f.get(F.get("breeds", ""))) if "breeds" in F else []
            st = sel(f.get(F["state"]))
            if st in ("Unknown", ""):
                st = None
            ps_years = {y for y, fid in PSY.items() if links(f.get(fid))}
            on_years = {y for y, fid in ONY.items() if links(f.get(fid))}
            adults = None
            if "adults" in F:
                m = re.search(r"\d+", str(f.get(F["adults"]) or ""))
                adults = int(m.group()) if m else None
            rows[r["id"]] = dict(
                kind=kind, lt=lt, sl=sl, st=st, cat=license_cat(lt), scat=seller_cat(lt),
                is_cat=is_cat(sl, breeds), breeds=breeds, adults=adults,
                cy=cancel_year(f.get(F["former"])), ps_years=ps_years, on_years=on_years,
                conn=ps_years | on_years,
                sells_ps=sel(f.get(F["ps"])) == "Yes",
                online=sel(f.get(F.get("online", ""))) == "Yes" if "online" in F else bool(on_years),
                web=sel(f.get(F.get("web", ""))) == "Yes" if "web" in F else False,
                tobroker=sel(f.get(F.get("tobroker", ""))) == "Yes" if "tobroker" in F else False,
                v=num(f.get(F["nci"])) > 0, sv=num(f.get(F["serious"])) > 0, insp=num(f.get(F["insp"])) > 0,
                dual=sl in ("State Licensed", "State Licensed Breeder", "Holds Second License"),
            )
    return rows


# ----------------------------------------------------------------------------
# Dashboard 1: Licensee analysis
# ----------------------------------------------------------------------------
def build_licensee(P, insp):
    rows = [p for p in P.values() if p["cat"] and p["st"]]
    C = collections.Counter(p["cat"] for p in rows)
    act = [p for p in rows if p["cat"] == "active"]
    cu = [p for p in rows if p["cat"] == "cusda"]
    for p in cu:
        p["conf"] = bool(p["cy"] and any(y > p["cy"] for y in p["conn"]))
        p["same"] = bool(p["cy"] and not p["conf"] and p["cy"] in p["conn"])
    cited = sorted(sel(r["f"].get(IN["date"])) for r in insp
                   if r["f"].get(IN["date"]) and num(r["f"].get(IN["direct"])) + num(r["f"].get(IN["critical"])) + num(r["f"].get(IN["noncrit"])) > 0)
    nat = dict(active=C["active"], state=C["state"], cusda=C["cusda"], cstate=C["cstate"], unlic=C["unlic"],
               activeViol=sum(p["v"] for p in act), activeSerious=sum(p["sv"] for p in act),
               dual=sum(p["dual"] for p in act),
               formerUsda=sum(1 for p in rows if p["cat"] == "state" and "Cancelled USDA" in p["sl"]),
               withYear=sum(1 for p in cu if p["cy"]), confirmed=sum(p["conf"] for p in cu),
               sameYear=sum(p["same"] for p in cu),
               inspFrom=cited[0][:4] if cited else "", inspTo=cited[-1][:10] if cited else "",
               pre2005=sum(1 for p in cu if p["cy"] and p["cy"] < 2005),
               ps=sum(p["sells_ps"] for p in rows), cats=sum(p["is_cat"] for p in rows))
    years = collections.Counter(p["cy"] for p in cu if p["cy"])
    cyears = collections.Counter(p["cy"] for p in cu if p["conf"])
    timeline = [dict(y=y, n=years.get(y, 0), c=cyears.get(y, 0)) for y in range(2005, THIS_YEAR + 1)]
    S = collections.defaultdict(collections.Counter)
    for p in rows:
        s = S[p["st"]]
        s[p["cat"]] += 1
        if p["cat"] == "active":
            s["v"] += p["v"]; s["dual"] += p["dual"]
        if p["cat"] == "cusda":
            s["conf"] += p["conf"]; s["wy"] += bool(p["cy"])
        if p["sells_ps"]:
            s["ps"] += 1; s["ps_" + p["cat"]] += 1
    states = [dict(st=k, **{a: b for a, b in v.items() if b}) for k, v in sorted(S.items())]
    return dict(nat=nat, timeline=timeline, states=states)


# ----------------------------------------------------------------------------
# Dashboard 2: Online sellers
# ----------------------------------------------------------------------------
SITE_MIN = 250
GROUP = {"active": "active", "state": "state", "cusda": "cusda", "cstate": "cstate", "unlic": "nolic", "other": "other"}


def build_online(P, sites, cases):
    S = {}
    for r in sites:
        f = r["f"]
        ids = set()
        for y, (b, k) in WS_SUP.items():
            ids |= set(links(f.get(b))) | set(links(f.get(k)))
        ids = {i for i in ids if i in P}
        S[sel(f.get(WS["name"]))] = dict(ids=ids, type=sel(f.get(WS["type"])))
    top = sorted([n for n, s in S.items() if n and len(s["ids"]) >= SITE_MIN], key=lambda n: -len(S[n]["ids"]))
    out_sites, allids = [], collections.Counter()
    for n in top:
        ids = S[n]["ids"]
        for i in ids:
            allids[i] += 1
        st = collections.Counter(P[i]["st"] for i in ids if P[i]["st"])
        out_sites.append(dict(name=n, type="broker" if S[n]["type"] == "Third Party Broker" else "market",
                              total=len(ids), mix=dict(collections.Counter(GROUP[P[i]["scat"]] for i in ids)),
                              states=[[a, b] for a, b in st.most_common()], nstates=len(st)))
    union = set(allids)
    st_all = collections.Counter(P[i]["st"] for i in union if P[i]["st"])
    multi_c = collections.Counter(min(v, 4) for v in allids.values())
    overlap = {a: {b: len(S[a]["ids"] & S[b]["ids"]) for b in top if b != a} for a in top}
    return dict(sites=out_sites, overlap=overlap, unique=len(union),
                multi={str(k): v for k, v in sorted(multi_c.items())},
                mixAll=dict(collections.Counter(GROUP[P[i]["scat"]] for i in union)),
                nStatesAll=len(st_all), topStatesAll=[[a, b] for a, b in st_all.most_common(10)],
                tracked=len([n for n in S if n]), audit=build_audit(cases))


def build_audit(cases):
    gd = json.load(open(os.path.join(STATIC_DIR, "gooddog_summary.json")))
    cb_states = collections.Counter()
    markets = collections.Counter()
    xplat = 0
    for r in cases:
        f = r["f"]
        st = sel(f.get(CB["state"]))
        cb_states[US_STATES.get(st, st)] += 1
        for m in multi(f.get(CB["markets"])):
            markets[m] += 1
        xplat += bool(f.get(CB["xplat"]))
    states = []
    for s in gd["states"]:
        row = dict(s)
        row["cb"] = cb_states.get(s["st"], 0)
        states.append(row)
    return dict(gd=dict(total=gd["total"], deliv=gd["deliv"], third=gd["third"], both=gd["both"], stth=gd["stth"]),
                cb=dict(total=len(cases), puppies=markets.get("Puppies.com", 0), akc=markets.get("AKC Marketplace", 0),
                        xplat=xplat), states=states)


# ----------------------------------------------------------------------------
# Dashboard 3: Pet store sourcing
# ----------------------------------------------------------------------------
PS_GROUP = {"active": "active", "cusda": "cusda", "state": "state", "cstate": "state", "unlic": "nolic", "other": "other"}


def build_petstores(P, stores):
    rows = []
    for r in stores:
        f = r["f"]
        if sel(f.get(PS["status"])) != "Open":
            continue
        b, k = set(), set()
        for y, (fb, fk) in PS_SUP.items():
            b |= set(links(f.get(fb))); k |= set(links(f.get(fk)))
        rows.append(dict(st=sel(f.get(PS["state"])), b={i for i in b if i in P}, k={i for i in k if i in P}))
    withs = [s for s in rows if s["b"] | s["k"]]
    sup = lambda s: s["b"] | s["k"]
    U = set().union(*[sup(s) for s in withs]) if withs else set()
    inspected = [i for i in U if P[i]["insp"]]
    supst = collections.Counter(P[i]["st"] for i in U if P[i]["st"])
    F = collections.defaultdict(collections.Counter)
    instate = collections.Counter()
    for s in withs:
        for i in sup(s):
            if P[i]["st"]:
                F[s["st"]][P[i]["st"]] += 1
            instate[s["st"]] += P[i]["st"] == s["st"]
    NS = collections.Counter(s["st"] for s in rows)
    NW = collections.Counter(s["st"] for s in withs)
    states = [dict(st=st, open=NS[st], withs=NW[st], links=sum(F[st].values()), instate=instate[st],
                   top=[[a, b] for a, b in F[st].most_common(5)]) for st in sorted(x for x in NS if x)]
    W = len(withs)
    sizes = sorted(len(sup(s)) for s in withs)
    return dict(
        nOpen=len(rows), nWith=W, nSup=len(U),
        nBreeder=sum(P[i]["kind"] == "breeder" for i in U), nBroker=sum(P[i]["kind"] == "broker" for i in U),
        mix=dict(collections.Counter(PS_GROUP[P[i]["scat"]] for i in U)),
        anyBroker=sum(1 for s in withs if s["k"]),
        halfBroker=sum(1 for s in withs if len(s["k"]) / len(sup(s)) >= .5),
        brokerOnly=sum(1 for s in withs if s["k"] and not s["b"]),
        allOut=sum(1 for s in withs if all(P[i]["st"] != s["st"] for i in sup(s))),
        anyViol=sum(1 for s in withs if any(P[i]["v"] for i in sup(s))),
        anySer=sum(1 for s in withs if any(P[i]["sv"] for i in sup(s))),
        anyNolic=sum(1 for s in withs if any(P[i]["scat"] == "unlic" for i in sup(s))),
        anyCusda=sum(1 for s in withs if any(P[i]["scat"] == "cusda" for i in sup(s))),
        medSup=sizes[len(sizes) // 2] if sizes else 0,
        supInsp=len(inspected), supCited=sum(P[i]["v"] for i in inspected), supSerious=sum(P[i]["sv"] for i in inspected),
        supStates=[[a, b] for a, b in supst.most_common(12)], nSupStates=len(supst), states=states,
        years=f"{min(PS_SUP)} to {max(PS_SUP)}")


# ----------------------------------------------------------------------------
# Shared scope for the breeder and broker dashboards:
# active USDA, state licensed, unlicensed active sellers, plus former
# licensees (USDA or state) still documented selling in the last three years.
# ----------------------------------------------------------------------------
def in_active_scope(p):
    if p["cat"] in ("active", "state", "unlic"):
        return True
    return p["cat"] in ("cusda", "cstate") and bool(p["conn"] & RECENT_YEARS)


def bucket(n):
    return 0 if n <= 4 else 1 if n < 20 else 2 if n < 50 else 3 if n < 100 else 4


def build_breeders(P, audit):
    br = [p for p in P.values() if p["kind"] == "breeder" and in_active_scope(p)]
    lic = [p for p in br if p["cat"] != "unlic" and p["adults"] is not None]
    bad = sum(1 for p in lic if p["adults"] > 1000)
    lic = [p for p in lic if p["adults"] <= 1000]
    size = {}
    for k in ("active", "state", "cusda"):
        g = sorted(p["adults"] for p in lic if p["cat"] == k)
        if len(g) >= 10:
            c = collections.Counter(bucket(x) for x in g)
            size[k] = dict(n=len(g), med=int(statistics.median(g)), b=[c[i] for i in range(5)])
    ch = {}
    for k in ("active", "state", "unlic", "cusda"):
        g = [p for p in br if p["cat"] == k]
        ch[k] = dict(n=len(g), ps=sum(p["sells_ps"] for p in g), on=sum(p["online"] for p in g),
                     web=sum(p["web"] for p in g), tob=sum(p["tobroker"] for p in g))
    breeds = collections.Counter(b for p in br for b in p["breeds"] if not b.lower().startswith("cat"))
    act = [p for p in br if p["cat"] == "active"]
    states = []
    for st in sorted({p["st"] for p in br if p["st"]}):
        g = [p for p in br if p["st"] == st]
        a = [p for p in g if p["cat"] == "active"]
        L = sorted(p["adults"] for p in lic if p["st"] == st)
        states.append(dict(st=st, n=len(g), active=len(a), state=sum(p["cat"] == "state" for p in g),
                           unlic=sum(p["cat"] == "unlic" for p in g),
                           med=int(statistics.median(L)) if len(L) >= 10 else None,
                           ps=sum(p["sells_ps"] for p in g), v=sum(p["v"] for p in a)))
    return dict(total=len(br), cats=dict(collections.Counter(p["cat"] for p in br)), acBad=bad, size=size,
                nSize=len(lic), n100=sum(1 for p in lic if p["adults"] >= 100), ch=ch,
                noChan=sum(1 for p in br if not (p["sells_ps"] or p["online"] or p["web"] or p["tobroker"])),
                nBreeds=sum(1 for p in br if p["breeds"]), breeds=breeds.most_common(12),
                actViol=sum(p["v"] for p in act), actSer=sum(p["sv"] for p in act),
                nCat=sum(p["is_cat"] for p in br), states=states,
                review=dict(profiles=audit["gd"]["total"] + audit["cb"]["total"], both=audit["gd"]["both"]),
                recentYears=f"{min(RECENT_YEARS)} to {max(RECENT_YEARS)}")


def build_brokers(P, stores):
    store_state = {r["id"]: sel(r["f"].get(PS["state"])) for r in stores}
    kr = [p for p in P.values() if p["kind"] == "broker" and in_active_scope(p)]
    kr_ids = [i for i, p in P.items() if p["kind"] == "broker" and in_active_scope(p)]
    # stores each broker supplied (from the pet store side, so it matches the pet store dashboard)
    reach = collections.defaultdict(set)
    for r in stores:
        f = r["f"]
        for y, (fb, fk) in PS_SUP.items():
            for i in links(f.get(fk)):
                reach[i].add(r["id"])
    sel_ids = [i for i in kr_ids if reach.get(i)]
    allstores = set().union(*[reach[i] for i in sel_ids]) if sel_ids else set()
    top10 = sorted(sel_ids, key=lambda i: -len(reach[i]))[:10]
    cnt = [len(reach[i]) for i in sel_ids]
    lk = [(P[i]["st"], store_state.get(s)) for i in sel_ids for s in reach[i] if store_state.get(s)]
    home = collections.Counter(P[i]["st"] for i in kr_ids if P[i]["st"])
    nsel = collections.Counter(P[i]["st"] for i in sel_ids)
    hreach = collections.defaultdict(set)
    for i in sel_ids:
        hreach[P[i]["st"]] |= reach[i]
    S = collections.defaultdict(collections.Counter)
    for i in kr_ids:
        p = P[i]
        if not p["st"]:
            continue
        s = S[p["st"]]; s["n"] += 1; s[p["cat"]] += 1
        if reach.get(i):
            s["sel"] += 1
        if p["cat"] == "active":
            s["v"] += p["v"]
    states = [dict(st=st, **dict(v), reach=len(hreach[st])) for st, v in S.items()]
    a = [p for p in kr if p["cat"] == "active"]
    onl = [i for i in kr_ids if P[i]["on_years"] & RECENT_YEARS]
    return dict(total=len(kr), cats=dict(collections.Counter(p["cat"] for p in kr)),
                nSel=len(sel_ids), nStores=len(allstores),
                top10=len(set().union(*[reach[i] for i in top10])) if top10 else 0,
                dist=[sum(1 for x in cnt if x == 1), sum(1 for x in cnt if 2 <= x <= 4), sum(1 for x in cnt if 5 <= x <= 19),
                      sum(1 for x in cnt if 20 <= x <= 49), sum(1 for x in cnt if x >= 50)],
                links=len(lk), cross=sum(1 for h, s in lk if h != s), storeStates=len({s for h, s in lk}),
                home=[[s, n, nsel[s], len(hreach[s])] for s, n in home.most_common(10)],
                selMix=dict(collections.Counter(P[i]["cat"] for i in sel_ids)),
                onl=len(onl), both=sum(1 for i in onl if reach.get(i)),
                actN=len(a), actViol=sum(p["v"] for p in a), actSer=sum(p["sv"] for p in a),
                nCat=sum(p["is_cat"] for p in kr), states=states)


# ----------------------------------------------------------------------------
# Dashboard 6: USDA Annual Audit
# ----------------------------------------------------------------------------
SEV = ["Direct", "Direct (Repeat)", "Critical", "Critical (Repeat)", "Non-Critical", "Non-Critical (Repeat)"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def build_usda(insp):
    narr = json.load(open(os.path.join(STATIC_DIR, "usda_narratives.json")))
    Y = collections.defaultdict(list)
    for r in insp:
        f = r["f"]
        d = sel(f.get(IN["date"]))
        cls = sel(f.get(IN["cls"]))
        if not d or cls not in ("Class A - Breeder", "Class B - Dealer"):
            continue
        Y[int(d[:4])].append(f)
    years = {}
    for y in sorted(Y):
        if y < 2021:
            continue
        recs = Y[y]
        sev = collections.Counter(s for f in recs for s in multi(f.get(IN["sev"])))
        vio = sum(1 for f in recs if multi(f.get(IN["sev"])))
        total = len(recs)
        st = collections.Counter(sel(f.get(IN["state"])) for f in recs if f.get(IN["state"]))
        stv = collections.Counter(sel(f.get(IN["state"])) for f in recs if f.get(IN["state"]) and multi(f.get(IN["sev"])))
        cats = collections.Counter(c for f in recs for c in multi(f.get(IN["cats"])))
        rate_states = sorted(([s, round(100 * stv[s] / n, 1), n] for s, n in st.items() if n >= 15), key=lambda x: -x[1])[:5]
        last = max(sel(f.get(IN["date"])) for f in recs)
        partial = y == THIS_YEAR
        rate = round(100 * vio / total, 1) if total else 0
        D = dict(total=total, vio=vio, clean=total - vio, rate=rate,
                 direct=sev["Direct"] + sev["Direct (Repeat)"], critical=sev["Critical"] + sev["Critical (Repeat)"],
                 noncrit=sev["Non-Critical"] + sev["Non-Critical (Repeat)"], totalNCIs=sum(sev[k] for k in SEV),
                 classA=sum(1 for f in recs if sel(f.get(IN["cls"])) == "Class A - Breeder"),
                 classB=sum(1 for f in recs if sel(f.get(IN["cls"])) == "Class B - Dealer"),
                 states=st.most_common(5), cats=cats.most_common(5), rateStates=rate_states,
                 severity={k: sev[k] for k in SEV if sev[k]})
        month = MONTHS[int(last[5:7]) - 1]
        if partial:
            D["partial"] = True
            D["asOf"] = f"{month} {y}"
            D["headline"] = f"Year in progress, data through {month}."
            D["note"] = (f"{y} is still in progress. Through {month}, {total:,} inspections have been logged with a "
                         f"{rate:.1f}% violation rate. USDA posts inspection reports with a delay of about four weeks, "
                         f"so the most recent weeks may still be undercounted. Treat this tab as a partial snapshot, "
                         f"not a year-end total.")
        elif str(y) in narr:
            D.update(narr[str(y)])
        else:
            D["headline"] = f"{rate:.1f}% of inspections found at least one violation."
            D["note"] = (f"{y} recorded {total:,} Class A/B dog and cat inspections, with {vio:,} finding at least one "
                         f"violation. The most frequently cited issue was: {cats.most_common(1)[0][0] if cats else 'n/a'}.")
        years[str(y)] = D
    return dict(years=years)


# ----------------------------------------------------------------------------
# Safety check and writing
# ----------------------------------------------------------------------------
CHECKS = {"licensee": lambda d: [d["nat"]["active"], d["nat"]["state"], d["nat"]["cusda"]],
          "online-sellers": lambda d: [d["unique"]],
          "pet-store-sourcing": lambda d: [d["nOpen"], d["nSup"]],
          "breeders": lambda d: [d["total"]],
          "brokers": lambda d: [d["total"]],
          "usda": lambda d: [sum(v["total"] for v in d["years"].values())]}


def safe_to_publish(name, new):
    path = os.path.join(OUT_DIR, f"{name}.json")
    if not os.path.exists(path):
        return True
    try:
        old = json.load(open(path))
        for o, n in zip(CHECKS[name](old), CHECKS[name](new)):
            if o and n < o * (1 - MAX_DROP):
                print(f"STOPPED: {name} dropped from {o} to {n}. Nothing was published. "
                      f"Check Airtable, then run again (or raise MAX_DROP if the drop is real).")
                return False
    except Exception as e:  # unreadable old file: publish the new one
        print(f"  (could not compare {name}: {e})")
    return True


def main(data=None):
    breeders, brokers, stores, sites, insp, cases = data or load()
    P = people(breeders, brokers)
    asof = TODAY.strftime("%B %-d, %Y")
    online = build_online(P, sites, cases)
    out = {"licensee": build_licensee(P, insp), "online-sellers": online,
           "pet-store-sourcing": build_petstores(P, stores),
           "breeders": build_breeders(P, online["audit"]), "brokers": build_brokers(P, stores),
           "usda": build_usda(insp)}
    os.makedirs(OUT_DIR, exist_ok=True)
    if not all(safe_to_publish(k, v) for k, v in out.items()):
        sys.exit(1)
    for k, v in out.items():
        v["asOf"] = asof
        with open(os.path.join(OUT_DIR, f"{k}.json"), "w") as fh:
            json.dump(v, fh, separators=(",", ":"), ensure_ascii=False)
        print(f"  wrote {k}.json")
    with open(os.path.join(OUT_DIR, "status.json"), "w") as fh:
        json.dump({"updated": dt.datetime.utcnow().isoformat() + "Z", "asOf": asof}, fh)
    print("Done.")
    return out


if __name__ == "__main__":
    main()
