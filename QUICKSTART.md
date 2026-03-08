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
