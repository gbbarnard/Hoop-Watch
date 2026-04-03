-- Quick checks for roster + player stats

-- 1) Show a team's roster from the players table.
-- Replace 9 with the internal team_id you want to inspect.
SELECT
    player_id,
    nba_player_id,
    CONCAT(first_name, ' ', last_name) AS player_name,
    team_id,
    position,
    jersey_number,
    height_in,
    weight_lb,
    birth_date,
    headshot_url
FROM players
WHERE team_id = 9
ORDER BY
    CASE WHEN jersey_number IS NULL THEN 999 ELSE jersey_number END,
    last_name,
    first_name;

-- 2) Show players that are still missing a season stats row.
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

-- 3) Inspect one player's season stat row.
-- Replace 12749 with the player_id you want to inspect.
SELECT *
FROM player_regular_season_stats
WHERE player_id = 12749;
