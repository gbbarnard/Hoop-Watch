# Roster Dropdown + Player Stats Guide

This is the shortest path for anyone on the team who only needs the **team roster dropdown** and the **player stats dropdown** working.

## The 3 files that matter most

### 1) `app.py`
This is the backend.

Important routes:
- `GET /api/teams/<team_id>/roster`
- `GET /api/teams/<team_id>/players`  
  Same roster data as `/roster`. Both routes work.
- `GET /api/players/<player_id>/stats`

Important helper functions:
- `_load_team_roster_from_db(cursor, team_id)`
- `_load_player_row(cursor, player_id)`
- `_load_player_regular_stats_from_db(cursor, player_id)`
- `_build_player_stats_response(cursor, player_row)`

### 2) `team-detail.js`
This is where the team page opens the roster and player stat dropdowns.

Important functions:
- `fetchTeamRoster(teamId)`
- `loadRosterForTeam(teamId, tbody)`
- `toggleRosterPlayerStats(row)`
- `renderPlayerStatsTable(payload, player)`
- `displayRoster(players)`

### 3) `database/sql/roster_player_stats_checks.sql`
Use this file in MySQL Workbench when you want to quickly check whether the roster rows and stat rows are present.

---

## How the dropdown works

### Team roster dropdown flow
1. `team-detail.html` loads `team-detail.js`
2. `fetchTeamData()` runs
3. frontend calls:
   - `/api/teams/<team_id>/roster`
4. backend reads from the `players` table
5. frontend renders each player row in the roster table

### Player stats dropdown flow
1. user clicks a player row in the roster
2. `toggleRosterPlayerStats(row)` runs
3. frontend calls:
   - `/api/players/<player_id>/stats`
4. backend reads:
   - player bio info from `players`
   - season stats from `player_regular_season_stats`
   - cached box score fallback if DB stats are missing
5. frontend shows the info cards + season stats table

---

## What tables power this

### `players`
Used for:
- roster list
- player name
- jersey number
- position
- height
- weight
- age
- headshot
- linking a clicked roster row to a player id

### `player_regular_season_stats`
Used for:
- GP
- MIN
- FG%
- 3P%
- FT%
- REB
- AST
- BLK
- STL
- PF
- TO
- PTS
- season label

If a player is in `players` but missing in `player_regular_season_stats`, the roster still loads, but the player stats route may fall back to cached box score totals or show a message that local stats are missing.

---

## Fast checks for teammates

### Check roster rows for a team
```sql
SELECT player_id, nba_player_id, first_name, last_name, team_id, position, jersey_number
FROM players
WHERE team_id = 9
ORDER BY jersey_number, last_name, first_name;
```

### Check if a clicked player has a season stat row
```sql
SELECT *
FROM player_regular_season_stats
WHERE player_id = 12749;
```

### Find players that are on rosters but still missing a stat row
```sql
SELECT
    p.player_id,
    p.nba_player_id,
    CONCAT(p.first_name, ' ', p.last_name) AS player_name,
    p.team_id,
    p.position,
    p.jersey_number,
    CASE WHEN s.player_id IS NULL THEN 'NO_STATS' ELSE 'HAS_STATS' END AS stats_status
FROM players p
LEFT JOIN player_regular_season_stats s
    ON p.player_id = s.player_id
WHERE s.player_id IS NULL
ORDER BY p.team_id, p.last_name, p.first_name;
```

---

## Important notes

### `/roster` and `/players` both work now
To make the backend easier to understand, the roster endpoint now has a clearer alias:
- `/api/teams/<team_id>/roster`

The old route still works too:
- `/api/teams/<team_id>/players`

That means older frontend code does not break.

### Zero-stat rows are allowed
If someone inserts a zero-stat row for a player, the stats endpoint now still returns a valid response instead of treating `gp = 0` like “no row exists.”

### The `to` alias SQL bug is fixed
The stats loader now safely quotes SQL aliases, so fields like `to` no longer crash MySQL.

---

## Scripts that help refill missing data

### Sync rosters into `players`
```bash
python app.py
# then hit /api/admin/sync-players as admin
```

### Fill stats without a paid API
```bash
python sync_player_stats_free.py --refresh-cache --repair-bad-cache --only-missing --current-team-only
```

### Audit bad NBA player ids
```bash
python audit_repair_nba_player_ids.py --only-missing-stats
```

Apply fixes:
```bash
python audit_repair_nba_player_ids.py --only-missing-stats --apply
```

---

## Best place to edit if something breaks again

### Roster does not load
Check:
- `team-detail.js` → `fetchTeamRoster()`
- `app.py` → `get_team_players()`
- `players` table rows for that team

### Player dropdown opens but stats are empty
Check:
- `team-detail.js` → `toggleRosterPlayerStats()`
- `app.py` → `get_player_stats()`
- `player_regular_season_stats` rows for that player
- cached box score files in `database/game_detail_cache/`

### Team page loads by NBA id instead of internal team id
Check:
- `team-detail.js` → `resolveInternalTeamId()`

---

## Recommended teammate workflow

1. Use `team-detail.html?id=<internal_team_id>` when possible.
2. If roster is empty, check the `players` table first.
3. If roster works but one player has no stats, check `player_regular_season_stats`.
4. If many players are missing stats, run the free sync script.
5. If only a few players are wrong, audit/fix `nba_player_id` values or insert zero-stat rows temporarily.
