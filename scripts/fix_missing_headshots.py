import re
import unicodedata
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

SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}

def strip_accents(s: str) -> str:
    # Dončić -> Doncic
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(ch)
    )

def clean_name(s: str) -> str:
    s = strip_accents(s or "")
    s = s.replace(".", " ").replace("-", " ").replace("'", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def remove_suffix(last_name: str) -> str:
    # "Brown Jr." -> "Brown", "Jackson II" -> "Jackson"
    parts = clean_name(last_name).split()
    parts = [p for p in parts if p.upper() not in SUFFIXES]
    return " ".join(parts).strip()

def best_match(full_name: str):
    # Try exact full-name lookup
    results = nba_players.find_players_by_full_name(full_name)
    if not results:
        return None
    # prefer active
    active = [r for r in results if r.get("is_active")]
    return active[0] if active else results[0]

def best_match_fallback(first: str, last: str):
    # Fallback: last name search then filter by first name
    results = nba_players.find_players_by_last_name(last)
    if not results:
        return None
    first_l = first.lower()
    filtered = [r for r in results if r.get("full_name","").lower().startswith(first_l + " ")]
    if filtered:
        active = [r for r in filtered if r.get("is_active")]
        return active[0] if active else filtered[0]
    active = [r for r in results if r.get("is_active")]
    return active[0] if active else results[0]

def main():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)

    # Keep a set of already-used NBA IDs to avoid duplicate-key errors
    cur.execute("SELECT nba_player_id FROM players WHERE nba_player_id IS NOT NULL AND nba_player_id <> ''")
    used_ids = {str(r["nba_player_id"]) for r in cur.fetchall()}

    # Pull only players that are missing nba_player_id
    cur.execute("""
        SELECT player_id, first_name, last_name
        FROM players
        WHERE nba_player_id IS NULL OR nba_player_id = ''
    """)
    rows = cur.fetchall()

    updated = 0
    still_missing = 0
    conflicts = 0

    for row in rows:
        pid = row["player_id"]
        first = clean_name(row["first_name"])
        last = remove_suffix(row["last_name"])
        full = f"{first} {last}".strip()

        match = best_match(full)

        if not match:
            match = best_match_fallback(first, last)

        if not match:
            still_missing += 1
            continue

        nba_id = str(match["id"])
        if nba_id in used_ids:
            # Would violate UNIQUE(nba_player_id)
            conflicts += 1
            continue

        used_ids.add(nba_id)
        headshot_url = CDN.format(pid=nba_id)

        cur.execute(
            "UPDATE players SET nba_player_id=%s, headshot_url=%s WHERE player_id=%s",
            (nba_id, headshot_url, pid)
        )
        updated += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Updated: {updated}")
    print(f"Still missing (no match): {still_missing}")
    print(f"Skipped due to duplicate NBA ID conflicts: {conflicts}")

if __name__ == "__main__":
    main()