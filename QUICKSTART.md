# HoopWatch (Dilan) – Quick Start

## 1) Backend (Flask)
1. Create + activate a venv
2. Install deps:
   - `pip install -r requirements.txt`
3. Set your MySQL connection (optional, if you don't use a password you can skip):
   - Windows PowerShell:
     - `setx MYSQL_PASSWORD ""`
   - Or set `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_DB`

Run:
- `python app.py`

Backend runs on: `http://localhost:8000`

## 2) Database (MySQL Workbench)
Run these in order:
- `database/schema.sql`
- `database/sample_data.sql` (optional)

## 3) Frontend (Static pages)
Open your static server / dev server and visit:
- `index.html` (games)
- `teams.html`
- `team-detail.html?id=1610612747`
- `game-detail.html?id=<nba_game_id>`
- `qotd.html`

**Important:** The frontend JS calls the backend at `http://localhost:8000`.

For the roster dropdown + player stats flow, see `docs/ROSTER_PLAYER_STATS_GUIDE.md`.


## Ball Don't Lie player stat sync


1. Put your API key in `.env`:
   `BALLDONTLIE_API_KEY=your_key_here`
2. Run:
   `python sync_player_stats_balldontlie.py --only-missing`



## Free player stats sync (no paid APIs)

To fill `player_regular_season_stats` using only your local/cached NBA CDN box scores:

```bash
python sync_player_stats_free.py --refresh-cache --repair-bad-cache --only-missing --current-team-only
```

Windows:

```bat
sync_player_stats_free.bat
```

This script:
- refreshes any missing completed-game cache files from the NBA CDN
- repairs unreadable/empty cache files
- builds player regular-season stats from the cached box scores only
- leaves `players.team_id` alone so it does not break rosters
- writes a report to `database/player_stats_free_sync_report.json`


## Audit and repair bad NBA player IDs

Dry run for players missing stats only:

```bash
python audit_repair_nba_player_ids.py --only-missing-stats
```

Apply the suggested fixes to the `players.nba_player_id` values:

```bash
python audit_repair_nba_player_ids.py --only-missing-stats --apply
```

This uses only the local cached NBA CDN box score files. It will not guess when the match is ambiguous.


## One-time player bios backfill
Use this once when you want to fill missing player bio info like jersey number, position, height, weight, and birth date.

```bash
python sync_player_bios_once.py
```

It only fills missing player bio fields and does not overwrite good existing values with blanks.
