"""
Compute season-wide stats (TrueSkill, CCWM, OPR, DPR, W/L/T, Win Rate) for the
teams currently at Worlds.

Strategy: instead of iterating every event in the season (~15k events, blows
past the RobotEvents rate limit), hit /teams/{id}/matches per Worlds team,
dedupe by match id, then compute stats. Uses ~1570 API calls total.

  cache/team_matches.json  — deduped raw matches, keyed by match id
  static/season_stats.json — computed per-team output

Re-run whenever you want fresh stats. Delete the cache to re-fetch.
"""
import concurrent.futures as cf
import json
import os
import time
from collections import defaultdict

import numpy as np
import requests
from openskill.models import PlackettLuce
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import lsmr

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

SEASONS = {"hs": 197, "ms": 197, "u": 198}  # event key -> season id
WORLDS_EVENT_IDS = {64025, 64026, 64027}  # HS V5RC, MS V5RC, VURC — excluded
                                          # from season stats so live rankings
                                          # can be summed on top client-side.

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "team_matches.json")
OUTPUT = os.path.join("static", "season_stats.json")
WORKERS = 3
MAX_RETRIES = 8


def api_get(session, path, params=None):
    """GET with retry on 429 / 5xx, honoring Retry-After."""
    for attempt in range(MAX_RETRIES):
        r = session.get(API + path, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or 500 <= r.status_code < 600:
            sleep = float(r.headers.get("Retry-After", 0)) or min(120, 2 ** attempt)
            time.sleep(sleep)
            continue
        raise RuntimeError(f"{r.status_code} {r.url}: {r.text[:120]}")
    raise RuntimeError(f"max retries: {path} {params}")


def paged(session, path, params=None):
    page = 1
    while True:
        p = dict(params or {})
        p["page"] = page
        p["per_page"] = 250
        d = api_get(session, path, p)
        yield from d["data"]
        if len(d["data"]) < 250:
            return
        page += 1


def fetch_team_matches(team_id, season_id):
    """Return compact match dicts for one team across the full season."""
    s = requests.Session()
    out = []
    for m in paged(s, f"teams/{team_id}/matches", {"season[]": season_id}):
        alls = m.get("alliances") or []
        red = next((a for a in alls if a.get("color") == "red"), None)
        blue = next((a for a in alls if a.get("color") == "blue"), None)
        if not red or not blue:
            continue
        rs, bs = red.get("score"), blue.get("score")
        if rs is None or bs is None or (rs == 0 and bs == 0):
            continue
        red_teams = [t["team"]["name"] for t in red.get("teams", []) if not t.get("sitting")]
        blue_teams = [t["team"]["name"] for t in blue.get("teams", []) if not t.get("sitting")]
        if not red_teams or not blue_teams:
            continue
        out.append({
            "id": m["id"],
            "e": (m.get("event") or {}).get("id"),
            "t": m.get("started") or m.get("scheduled") or "",
            "n": m.get("name", ""),
            "r": red_teams,
            "b": blue_teams,
            "rs": rs,
            "bs": bs,
        })
    return out


def load_worlds_teams():
    """Return [(team_id, number, event_key, season_id), ...] from the pre-built teams.json."""
    with open(os.path.join("static", "teams.json"), encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for ev in data["events"]:
        for t in ev["teams"]:
            out.append((t["id"], t["number"], ev["key"], SEASONS[ev["key"]]))
    return out


def fetch_all_matches():
    if os.path.exists(CACHE_FILE):
        print(f"loading cache {CACHE_FILE}")
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)

    os.makedirs(CACHE_DIR, exist_ok=True)
    teams = load_worlds_teams()
    print(f"fetching matches for {len(teams)} Worlds teams...")

    merged = {}  # match_id -> match dict (deduped across teams)
    failed = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_team_matches, tid, sid): (tid, num)
                for (tid, num, _k, sid) in teams}
        for i, fut in enumerate(cf.as_completed(futs)):
            tid, num = futs[fut]
            try:
                for m in fut.result():
                    merged[m["id"]] = m
            except Exception as e:
                failed.append((tid, num))
                if len(failed) <= 5:
                    print(f"  team {num} ({tid}): {e}")
            if (i + 1) % 100 == 0:
                dt = time.time() - t0
                rate = (i + 1) / max(dt, 1)
                eta = (len(teams) - i - 1) / rate
                print(f"  {i + 1}/{len(teams)} teams ({rate:.1f}/s, ETA {eta:.0f}s), "
                      f"{len(merged)} unique matches, {len(failed)} failed")

    if failed and len(failed) < len(teams) // 4:
        season_by_tid = {tid: sid for (tid, _num, _k, sid) in teams}
        print(f"retrying {len(failed)} failed teams sequentially...")
        for tid, num in failed:
            try:
                for m in fetch_team_matches(tid, season_by_tid[tid]):
                    merged[m["id"]] = m
            except Exception as e:
                print(f"  team {num} giving up: {e}")

    matches = list(merged.values())
    print(f"fetched {len(matches)} unique matches in {time.time()-t0:.0f}s; writing cache")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f)
    return matches


def is_qualifier(name):
    n = name.lower().strip()
    if "practice" in n:
        return False
    return (
        n.startswith("qualifier")
        or n.startswith("qual ")
        or n.startswith("qual#")
        or n.startswith("q ")
        or n.startswith("q#")
        or n.startswith("q-")
        or (len(n) >= 2 and n[0] == "q" and n[1].isdigit())
    )


def fetch_worlds_match_ids():
    """Return the set of match ids at the three Worlds events, so we can exclude
    them from season stats and let the client sum live Worlds rankings on top.
    Uses the division-level matches endpoint — the event-level one 404s at Worlds."""
    s = requests.Session()
    ids = set()
    for eid in WORLDS_EVENT_IDS:
        try:
            info = api_get(s, f"events/{eid}")
            for div in info.get("divisions", []):
                try:
                    for m in paged(s, f"events/{eid}/divisions/{div['id']}/matches"):
                        ids.add(m["id"])
                except Exception as e:
                    print(f"  event {eid}/div {div['id']}: {e}")
        except Exception as e:
            print(f"  event {eid}: {e}")
    return ids


def compute_stats(matches):
    worlds_ids = fetch_worlds_match_ids()
    print(f"excluding {len(worlds_ids)} Worlds match ids from season stats")
    qual = [
        m for m in matches
        if is_qualifier(m["n"])
        and m.get("e") not in WORLDS_EVENT_IDS
        and m["id"] not in worlds_ids
    ]
    qual.sort(key=lambda m: m["t"])
    print(f"qualifier matches (excl. Worlds): {len(qual)}/{len(matches)}")

    team_idx = {}
    def idx(name):
        j = team_idx.get(name)
        if j is None:
            j = len(team_idx); team_idx[name] = j
        return j

    wins = defaultdict(int)
    losses = defaultdict(int)
    ties = defaultdict(int)

    model = PlackettLuce()
    ratings = {}

    ccwm_i, ccwm_j, ccwm_v, ccwm_b = [], [], [], []
    opr_i, opr_j, opr_v, opr_b, dpr_b = [], [], [], [], []
    m_i = 0
    a_i = 0

    for m in qual:
        rs, bs = m["rs"], m["bs"]
        red_teams, blue_teams = m["r"], m["b"]

        if rs > bs:
            for t in red_teams: wins[t] += 1
            for t in blue_teams: losses[t] += 1
            ranks = [0, 1]
        elif bs > rs:
            for t in blue_teams: wins[t] += 1
            for t in red_teams: losses[t] += 1
            ranks = [1, 0]
        else:
            for t in red_teams + blue_teams: ties[t] += 1
            ranks = [0, 0]

        red_r = [ratings.setdefault(t, model.rating(name=t)) for t in red_teams]
        blue_r = [ratings.setdefault(t, model.rating(name=t)) for t in blue_teams]
        try:
            new_red, new_blue = model.rate([red_r, blue_r], ranks=ranks)
            for k, t in enumerate(red_teams): ratings[t] = new_red[k]
            for k, t in enumerate(blue_teams): ratings[t] = new_blue[k]
        except Exception:
            pass

        for t in red_teams:
            ccwm_i.append(m_i); ccwm_j.append(idx(t)); ccwm_v.append(1)
        for t in blue_teams:
            ccwm_i.append(m_i); ccwm_j.append(idx(t)); ccwm_v.append(-1)
        ccwm_b.append(rs - bs)
        m_i += 1

        for t in red_teams:
            opr_i.append(a_i); opr_j.append(idx(t)); opr_v.append(1)
        opr_b.append(rs); dpr_b.append(bs); a_i += 1
        for t in blue_teams:
            opr_i.append(a_i); opr_j.append(idx(t)); opr_v.append(1)
        opr_b.append(bs); dpr_b.append(rs); a_i += 1

    n = len(team_idx)
    print(f"solving CCWM/OPR/DPR over {n} teams, {m_i} matches...")
    M = coo_matrix((ccwm_v, (ccwm_i, ccwm_j)), shape=(m_i, n)).tocsr()
    A = coo_matrix((opr_v, (opr_i, opr_j)), shape=(a_i, n)).tocsr()
    ccwm = lsmr(M, np.array(ccwm_b, dtype=np.float64))[0]
    opr = lsmr(A, np.array(opr_b, dtype=np.float64))[0]
    dpr = lsmr(A, np.array(dpr_b, dtype=np.float64))[0]

    out = {}
    for t, i in team_idx.items():
        r = ratings.get(t)
        w, l, ti = wins[t], losses[t], ties[t]
        tot = w + l + ti
        out[t] = {
            "trueskill": round(float(r.mu), 2) if r else None,
            "mu": round(float(r.mu), 2) if r else None,
            "sigma": round(float(r.sigma), 2) if r else None,
            "ccwm": round(float(ccwm[i]), 1),
            "opr": round(float(opr[i]), 1),
            "dpr": round(float(dpr[i]), 1),
            "wins": w, "losses": l, "ties": ti,
            "winrate": round(w / tot * 100, 1) if tot > 0 else None,
        }
    return out


def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    matches = fetch_all_matches()
    stats = compute_stats(matches)
    # Emit only the Worlds roster; computed stats for other teams are incidental.
    roster = {num for (_tid, num, _k, _s) in load_worlds_teams()}
    filtered = {k: v for k, v in stats.items() if k in roster}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(filtered, f, separators=(",", ":"))
    print(f"wrote {OUTPUT}  ({os.path.getsize(OUTPUT)/1024:.1f} KB, {len(filtered)} teams)")


if __name__ == "__main__":
    main()
