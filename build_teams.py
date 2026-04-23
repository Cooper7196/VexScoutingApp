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
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiZjc5MzgwNmVlOTU3"
    "ZmEyYzkyODk3YTdjMTcxOGE1Zjc2ZDZhNTcxODJlM2U5NmI4Mjc5OWIwNjllMjE3ZDQ4ZjJmY2Fl"
    "OTdjYmJmM2QzMDIiLCJpYXQiOjE2NzQ3OTg5OTAuMDk1NDkxOSwibmJmIjoxNjc0Nzk4OTkwLjA5"
    "NTQ5NTksImV4cCI6MjYyMTU3MDE5MC4wOTIwNDM5LCJzdWIiOiI4NDUxOSIsInNjb3BlcyI6W119"
    ".KglMyufEjUZ8WceNQJ2GMWj5e2qQsya1QPm7jHBhYg0cqOgCmWi2UqnaMqLsmJubv-Y5Mv-IWj"
    "kQ5E6bD8l57qGsvtGllvms_jW4KmdD8w9iDMo8YFNmuMN4OTt00gmOgOoBPZcSeYVwXJnQoX_WW"
    "OlxIyeGPKI11bxUNfJXr9xD4NhTG0wSQyS6yS53hh1XEJtDRzUw7Eeoq_PVWIzipmzOqeFnx2Nx"
    "HOeRpNQj9dGKNBPiTy1M42wiNi8bErONBfwikddQsk_xN2ePfqC1zsM9qL34pWm3enNPqVn92zT"
    "zp1fUiwQcBdPttWt-Y52Gy-VUYVnm5ZMq8s5Xk8pB2op5k9EOTl1-8r1BnSYJepwsJSaDRr_Jsu"
    "hwAvVTisemSKN7bM5dGjLcb8dr6peQLSXUMnedjmf2Kq3AjEOy-CeazL9tAOQ4kqHU75eNnWJek"
    "1J9ulSbuZiv3q3xNlKz_TWzLVItyKPB7JMZPqEmpoqnnUev1ZLNAYyZZDdG0sbRlnjP-Ad8paeo"
    "YSASpahoKMchc2FMVM3KaWa69XbKEQJ8sDsP3b0gLcXB_a_uq4NWMHm-0P9yqCGPOuz0NYzLGBf"
    "N-Kvq2GUzWxSbixxVp952ESdsiGIARq0yFn0c3Lvfp35UhjuggWHuFnGmVnqYCNjSMqBmWaP6K_"
    "BrxP39NMc"
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

    # Round-robin fallback for teams without a live ranking yet (matches the
    # original app's pre-event behavior). Sorted by team number for stability.
    unassigned = sorted([t for t in teams.values() if t["division"] is None],
                        key=lambda t: t["number"])
    if unassigned and divisions:
        for i, team in enumerate(unassigned):
            team["division"] = divisions[i % len(divisions)]["name"]
            team["division_source"] = "round-robin"
        print(f"[{ev['key']}] round-robin assigned {len(unassigned)} teams")

    # Join skills CSV
    skills = load_skills_csv(ev["skills_csv"])
    matched = 0
    for num, team in teams.items():
        if num in skills:
            team["skills"] = skills[num]
            matched += 1
    print(f"[{ev['key']}] skills matched: {matched}/{len(teams)}")

    return {
        "key": ev["key"],
        "id": ev["id"],
        "program": ev["program"],
        "label": ev["label"],
        "name": info["name"],
        "start": info.get("start"),
        "divisions": [d["name"] for d in divisions],
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
