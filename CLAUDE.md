# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Static site for scouting teams at the VEX Robotics World Championship. No server: a Python build script writes `static/teams.json`, and the browser does everything else — client-side routing, list rendering, and live fetches to the RobotEvents API for matches/awards.

Covers three events:
- **HS V5RC** (event id `64025`, key `hs`)
- **MS V5RC** (event id `64026`, key `ms`)
- **VURC** (event id `64027`, key `u`)

Seasons: V5RC = `197` (Push Back 2025-26), VURC = `198`.

## Running / developing

```bash
# 1. Regenerate the pre-built team data (run whenever you want fresh rankings)
python build_teams.py

# 2. Serve locally — use serve.py (not `python -m http.server`!) because the
#    built-in server 404s on SPA routes like /team/XXX/. serve.py falls back
#    to index.html for any missing file, matching what GitHub Pages does
#    via 404.html.
python serve.py 8765
# open http://localhost:8765/
```

Dependencies: `requests` (for the build script only). No runtime Python — the browser hits RobotEvents directly.

## Architecture

### `build_teams.py` — data pipeline

Produces `static/teams.json` with one entry per event. For each event:

1. `GET events/{id}` — event info + divisions. Wrap-level divisions (named "High School", "Middle School", "VEX U", "Elementary School") are filtered out by name; `order` is unreliable (it's `11` for HS/MS but `4` for VURC).
2. `GET events/{id}/teams` — base roster (team id, number, name, org, region).
3. `GET events/{id}/divisions/{d}/rankings` — real division assignments + W/L/T + rank + WP/AP/SP. Only populated once matches begin. Pre-event, all teams come back with `division: null`.
4. **Round-robin fallback** for any team still `division == null`, assigned by sorted team number. This matches the original Flask app's pre-event behavior. As soon as the event starts and rankings populate, step 3 overrides. The `division_source: "round-robin"` field is set on these.
5. `Skills CSV` is joined by team number (user-uploaded files, current Push Back season).

**Hardcoded RobotEvents bearer token** in `build_teams.py` and `static/app.js` — intentionally client-side, as the user confirmed. Treat as a public API key, not a secret.

### Browser SPA

- **`index.html`** — shell with jQuery + Bootstrap 5 + bootstrap-table. Includes the GH Pages redirect decoder (turns `/?/team/886Y/` back into `/team/886Y/` before the app boots).
- **`404.html`** — GH Pages SPA trick from rafgraph/spa-github-pages. Redirects unknown paths (`/team/886Y/`) to `/?/team/886Y/` so `index.html` can route client-side. `pathSegmentsToKeep = 0`; set to `1` if deploying to `username.github.io/VexScoutingApp/` project pages.
- **`static/app.js`** — single-file SPA. Routes:
  - `/` → nested tabs: top-level by event (HS/MS/U), sub-tabs by division, bootstrap-table per division with the original columns (Number, Division, Name, Region, Skills Rank/Score, True Skill, CCWM, W/L/T, Win Rate). True Skill / CCWM / Win Rate are `N/A` placeholders (see below).
  - `/team/XXX/` → team detail. Renders skills summary from `teams.json`, then live-fetches matches and season awards from RobotEvents. Red/blue alliance cells colored with `text-danger` / `text-primary`; current team bolded. Alliance size auto-detected per match (2v2 for V5RC, 3v3 for VURC).

### What's explicitly not implemented

- **TrueSkill / CCWM / win-probability predictions.** The original app pulled these from `vrc-data-analysis.com` (now down) + a season-wide xlsx. Placeholders show `N/A`. To add them back, either (a) compute locally from the season's matches via `openskill` and include in `teams.json`, or (b) wait for a new data source.
- **Comments.** Dropped at user request — static hosting target, no backend.

## Deployment

Serves as-is from any static host: GitHub Pages, Netlify, Cloudflare Pages, S3+CloudFront, etc. GitHub Pages needs both `index.html` and `404.html` at the root.
