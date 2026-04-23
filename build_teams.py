"""
Build static/teams.json for the scouting site.

Fetches the three Worlds events (HS V5RC, MS V5RC, VURC) from RobotEvents,
joins per-division rankings and skills CSVs, writes a single JSON blob.

Re-run whenever you want fresh rankings / match counts.
"""
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://www.robotevents.com/api/v2/"
TOKEN = os.environ.get("ROBOTEVENTS_TOKEN") or (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiZWE0OGRkYzYwNGQ5"
    "Yjk1OTAxYzIxYmE4ODY5YzkyMmY5MDc5MTdlYzY2MGY0ODdkNGIzZjdlNDNlZGFhMWRiMjZhZTk1"
    "ZDdmNDRmZDY5NDUiLCJpYXQiOjE3NzY5MTU1OTEuNzQ4MDM1LCJuYmYiOjE3NzY5MTU1OTEuNzQ4"
    "MDM3MSwiZXhwIjoyNzIzNjg2NzkxLjc0Mzc2Mywic3ViIjoiODQ1MTkiLCJzY29wZXMiOltdfQ."
    "isSuQ7leKbPrd5-taERi6xhY2iEv95cHQPxGZtsehpTe2ejZ2f8PIVxY2G3f8UlYdpNcsVn_Ohb"
    "_Zee1XzGg5cW012XgflKtxxKgSeYv7kJVx3aK0_uzLs7IDd2QZ87dS_JmUG5WLFQAQfQXKCe3cc"
    "UR2iSTf8_En2BnMgrjRX8BjtwDdEA0sdD8X9p4QgIBNF3C26ExrfXMxVTUYbqPIDoEJ-zyKiviF"
    "v7La3a2o64xZfRW4YW5NaFyz5iyk2gZUL3UNCqw7ucR5prKPbI3Npou8mu27fAIlMFqA8M2qKCL"
    "NNJzV56Ai7BX1RUb0lgAinchpTYjKisb48NkWviCvVm5J0lkhWYzG2_tVZkV1BRVkJdCB-jRpuc"
    "wNYvrR_r5J1ehNwKo6pYgYtHsyh2pTVrb8nylULePaeZBusxkDGL5CNFixijdL5WYBHxxxjKwxl"
    "GlbwOSD4T-hFEdceJhVm0tl-shH5GWIHsUeT0ci3S-7eQtcjyYbmnadUqogTGlGkjmxjtQhbiRf"
    "oqJ2YmwBnteL51K_moAkPufikJ1Dk2JwLlztF8leSgfagPWKCp6UjABfZbQ1jIJEw2ueND1qGAo"
    "yV2j1kC9qyJpC6QXxAMaSAVcPbO964WlPh_uzoGisdDJ2jFPVvhzwDkbQLjxhIe2BYJqHMnkZEn"
    "-0GLKW6Y"
)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "accept-language": "en"}

EVENTS = [
    {"key": "hs", "id": 64025, "program": "V5RC", "label": "High School (V5RC)",
     "skills_csv": "skills-standings V5RC HS.csv"},
    {"key": "ms", "id": 64026, "program": "V5RC", "label": "Middle School (V5RC)",
     "skills_csv": "skills-standings V5RC MS.csv"},
    {"key": "u",  "id": 64027, "program": "VURC", "label": "VEX U (VURC)",
     "skills_csv": "skills-standings VURC.csv"},
]


def api(path, **params):
    r = requests.get(API + path, headers=HEADERS, params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {path}: {r.text[:200]}")
    return r.json()


def paged(path, **params):
    """Yield all items across pages."""
    page = 1
    while True:
        params["page"] = page
        params.setdefault("per_page", 250)
        d = api(path, **params)
        yield from d["data"]
        if len(d["data"]) < params["per_page"]:
            return
        page += 1


def load_skills_csv(path):
    """Return {team_number: {rank, score, driver, auto}}."""
    out = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            num = row["Team Number"]
            out[num] = {
                "rank": int(row["Rank"]) if row.get("Rank") else None,
                "score": int(row["Score"]) if row.get("Score") else None,
                "driver": int(row["Driver Skills"]) if row.get("Driver Skills") else None,
                "auto": int(row["Autonomous Coding Skills"]) if row.get("Autonomous Coding Skills") else None,
            }
    return out


WRAP_DIVISION_NAMES = {"High School", "Middle School", "VEX U", "Elementary School"}


def load_manual_divisions():
    path = "divisions.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_season_stats():
    path = os.path.join("static", "season_stats.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_event(ev):
    print(f"[{ev['key']}] fetching event {ev['id']}...")
    info = api(f"events/{ev['id']}")
    # Real divisions — skip the event-wide wrap division (named after the grade bucket)
    divisions = [
        {"id": d["id"], "name": d["name"], "order": d.get("order", 0)}
        for d in info.get("divisions", [])
        if d["name"] not in WRAP_DIVISION_NAMES
    ]
    divisions.sort(key=lambda d: d["order"])
    print(f"[{ev['key']}] {len(divisions)} divisions")

    # Base team info (id, name, region, org) for every registered team
    print(f"[{ev['key']}] fetching event teams...")
    teams = {}
    for t in paged(f"events/{ev['id']}/teams"):
        teams[t["number"]] = {
            "number": t["number"],
            "id": t["id"],
            "name": t.get("team_name", ""),
            "organization": t.get("organization", ""),
            "region": (t.get("location") or {}).get("region") or "",
            "country": (t.get("location") or {}).get("country") or "",
            "grade": t.get("grade", ""),
            "division": None,
            "rank": None, "wins": 0, "losses": 0, "ties": 0,
            "wp": 0, "ap": 0, "sp": 0,
            "skills": None,
        }
    print(f"[{ev['key']}] {len(teams)} teams")

    # Rankings per division — fills division / W-L-T / rank
    for div in divisions:
        try:
            for r in paged(f"events/{ev['id']}/divisions/{div['id']}/rankings"):
                num = r["team"]["name"]
                if num not in teams:
                    continue
                teams[num]["division"] = div["name"]
                teams[num]["rank"] = r.get("rank")
                teams[num]["wins"] = r.get("wins", 0)
                teams[num]["losses"] = r.get("losses", 0)
                teams[num]["ties"] = r.get("ties", 0)
                teams[num]["wp"] = r.get("wp", 0)
                teams[num]["ap"] = r.get("ap", 0)
                teams[num]["sp"] = r.get("sp", 0)
        except Exception as e:
            print(f"  division {div['name']}: {e}")
        time.sleep(0.05)

    # Apply manual RECF division lists to any team still unassigned (i.e., the
    # event hasn't started so rankings don't exist yet). Live rankings above
    # always win. See divisions.json — derived from the PDFs at
    # https://recf.org/vex_worlds/division-lists/
    manual = load_manual_divisions().get(ev["key"], {})
    manual_count = 0
    for div_name, team_numbers in manual.items():
        for num in team_numbers:
            t = teams.get(num)
            if t and t["division"] is None:
                t["division"] = div_name
                t["division_source"] = "recf-pdf"
                manual_count += 1
    if manual_count:
        print(f"[{ev['key']}] RECF-PDF assigned {manual_count} teams")

    # Last-resort round-robin for anything still unassigned.
    unassigned = sorted([t for t in teams.values() if t["division"] is None],
                        key=lambda t: t["number"])
    if unassigned and divisions:
        for i, team in enumerate(unassigned):
            team["division"] = divisions[i % len(divisions)]["name"]
            team["division_source"] = "round-robin"
        print(f"[{ev['key']}] round-robin fallback for {len(unassigned)} teams")

    # Join skills CSV
    skills = load_skills_csv(ev["skills_csv"])
    matched = 0
    for num, team in teams.items():
        if num in skills:
            team["skills"] = skills[num]
            matched += 1
    print(f"[{ev['key']}] skills matched: {matched}/{len(teams)}")

    # Join season stats (TrueSkill, CCWM, OPR, DPR, season W/L/T, win rate)
    season_stats = load_season_stats()
    stats_matched = 0
    for num, team in teams.items():
        if num in season_stats:
            team["stats"] = season_stats[num]
            stats_matched += 1
    if season_stats:
        print(f"[{ev['key']}] season stats matched: {stats_matched}/{len(teams)}")

    return {
        "key": ev["key"],
        "id": ev["id"],
        "program": ev["program"],
        "label": ev["label"],
        "name": info["name"],
        "start": info.get("start"),
        "divisions": [d["name"] for d in divisions],
        "divisions_meta": [{"id": d["id"], "name": d["name"]} for d in divisions],
        "teams": list(teams.values()),
    }


def main():
    os.makedirs("static", exist_ok=True)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": [build_event(ev) for ev in EVENTS],
    }
    dest = os.path.join("static", "teams.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {dest} ({os.path.getsize(dest) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
