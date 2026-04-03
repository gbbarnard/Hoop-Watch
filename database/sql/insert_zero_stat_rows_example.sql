-- Example: insert zero-stat rows for players who should stay visible in roster/player dropdowns.
-- Replace the player_id list and season label as needed.

INSERT INTO player_regular_season_stats (
    player_id,
    season_label
)
SELECT p.player_id, '2025-26'
FROM players p
WHERE p.player_id IN (12848, 12774, 12787, 12785, 12714, 12973)
  AND NOT EXISTS (
      SELECT 1
      FROM player_regular_season_stats s
      WHERE s.player_id = p.player_id
  );
