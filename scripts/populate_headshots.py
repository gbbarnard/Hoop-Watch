import re
import mysql.connector
from nba_api.stats.static import players as nba_players

DB = {
    "host": "localhost",
    "user": "root",
    "password": "IzzyPop2025!",
    "database": "hoopwatch",
}

CDN = "https://cdn.nba.com/headshots/nba/latest/260x190/{pid}.png"
PLACEHOLDER = "/static/Headshots/placeholder.png"

def normalize(s: str) -> str:
    s = s.lower().strip()
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s)
    return s

def find_best(full_name: str):
    results = nba_players.find_players_by_full_name(full_name)
    if not results:
        results = nba_players.find_players_by_full_name(full_name.replace(".", ""))
    if not results:
        return None

    target = normalize(full_name)

    # exact match first
    for r in results:
        if normalize(r.get("full_name", "")) == target:
            return r

    # otherwise prefer active
    for r in results:
        if r.get("is_active"):
            return r

    return results[0]

def main():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)

    # Quick sanity check: show which DB you're connected to
    cur.execute("SELECT DATABASE() AS db")
    print("Connected to DB:", cur.fetchone()["db"])

    cur.execute("SELECT player_id, first_name, last_name, nba_player_id FROM players")
    rows = cur.fetchall()

    used_nba_ids = set()
    updated, missing, dupes = 0, 0, 0

    for row in rows:
        current = (row["nba_player_id"] or "").strip()

        # Skip players already set to a real numeric NBA id
        if current.isdigit():
            used_nba_ids.add(current)
            continue

        full_name = f'{row["first_name"]} {row["last_name"]}'.strip()
        match = find_best(full_name)

        if not match:
            cur.execute(
                "UPDATE players SET headshot_url=%s WHERE player_id=%s",
                (PLACEHOLDER, row["player_id"])
            )
            missing += 1
            continue

        nba_id = str(match["id"])

        # Prevent accidental duplicates if matching is off
        if nba_id in used_nba_ids:
            cur.execute(
                "UPDATE players SET headshot_url=%s WHERE player_id=%s",
                (PLACEHOLDER, row["player_id"])
            )
            dupes += 1
            continue

        used_nba_ids.add(nba_id)

        headshot_url = CDN.format(pid=nba_id)
        cur.execute(
            "UPDATE players SET nba_player_id=%s, headshot_url=%s WHERE player_id=%s",
            (nba_id, headshot_url, row["player_id"])
        )
        updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Updated: {updated}, Missing matches: {missing}, Duplicate-skips: {dupes}")

if __name__ == "__main__":
    main()