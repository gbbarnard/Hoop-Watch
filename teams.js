const API_BASE = "http://localhost:8000";

const teamsEl = document.getElementById("teams");
const searchInput = document.getElementById("searchInput");
const confSelect = document.getElementById("confSelect");
const sortSelect = document.getElementById("sortSelect");

const FAVORITES_KEY = "hoopwatch.favoriteTeams";

let ALL_TEAMS = [];

function loadFavoriteIds() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.map((v) => String(v));
  } catch (err) {
    console.error("Failed to parse favorites:", err);
    return [];
  }
}

function saveFavoriteIds(ids) {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(ids));
}

function showToast(message) {
  const existing = document.querySelector(".toast-message");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast-message";
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 2200);
}

function isFavoriteTeam(teamId) {
  const ids = loadFavoriteIds();
  return ids.includes(String(teamId));
}

function toggleFavoriteTeam(teamId) {
  const target = String(teamId);
  const ids = loadFavoriteIds();
  const exists = ids.includes(target);
  const next = exists ? ids.filter((id) => id !== target) : [...ids, target];
  saveFavoriteIds(next);
  showToast(exists ? "Favorite team removed" : "Favorite team added");
  updateView();
}

function nbaLogoUrl(teamId) {
  return `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`;
}

function safeText(v) {
  return (v ?? "").toString();
}

function computeDisplayName(team) {
  // In our DB, `name` is usually full_name already (e.g., "Atlanta Hawks").
  // Avoid "Atlanta Atlanta Hawks" by not blindly concatenating city + name.
  const name = safeText(team.name);
  const city = safeText(team.city);
  if (!name) return city || "Team";
  if (city && name.toLowerCase().startsWith(city.toLowerCase())) return name;
  return city ? `${city} ${name}` : name;
}

function createTeamCard(team) {
  const wrapper = document.createElement("div");
  wrapper.className = "team-card";

  const favorite = isFavoriteTeam(team.id);

  const favBtn = document.createElement("button");
  favBtn.type = "button";
  favBtn.className = `team-fav-star${favorite ? " is-favorite" : ""}`;
  favBtn.setAttribute("aria-pressed", favorite ? "true" : "false");
  favBtn.setAttribute("aria-label", favorite ? "Remove favorite" : "Add favorite");
  favBtn.title = favorite ? "Favorited" : "Add favorite";
  favBtn.textContent = "★";
  favBtn.addEventListener("click", (evt) => {
    evt.preventDefault();
    evt.stopPropagation();
    toggleFavoriteTeam(team.id);
  });

  wrapper.appendChild(favBtn);

  const a = document.createElement("a");
  // `team.id` is the INTERNAL DB id
  a.href = `team-detail.html?id=${team.id}`;

  const displayName = computeDisplayName(team);
  const abbr = safeText(team.abbreviation);
  const conf = safeText(team.conference);

  const wins = Number(team.wins || 0);
  const losses = Number(team.losses || 0);
  const pct = wins + losses > 0 ? (wins / (wins + losses)) : 0;
  const pctText = (pct * 100).toFixed(1);

  // `team.nba_team_id` is the NBA id used for CDN logos
  const nbaId = team.nba_team_id || team.nbaId || null;
  const fallbackLogo = nbaId ? nbaLogoUrl(nbaId) : "";
  const logoSrc = team.logo_url || fallbackLogo;

  a.innerHTML = `
    <div class="team-card-logo">
      <img src="${logoSrc}" alt="${displayName}" loading="lazy"
        style="width:100%;height:100%;object-fit:contain;"
        onerror="this.onerror=null;${nbaId ? `this.src='${nbaLogoUrl(nbaId)}';` : "this.style.display='none';"}" />
    </div>
    <div class="team-info">
      <h3>${displayName}</h3>
      <div class="team-city">${abbr}${conf ? ` • ${conf}` : ""}</div>
      <div class="team-record">${wins}-${losses}</div>
      <div class="team-win-rate">Win Rate: ${pctText}%</div>
    </div>
  `;

  wrapper.appendChild(a);
  return wrapper;
}

function applyFilters(teams) {
  const q = safeText(searchInput.value).trim().toLowerCase();
  const conf = safeText(confSelect.value);

  return teams.filter((t) => {
    if (conf !== "all" && safeText(t.conference) !== conf) return false;

    if (!q) return true;
    const hay = [t.name, t.city, t.abbreviation, t.conference]
      .map((x) => safeText(x).toLowerCase())
      .join(" ");
    return hay.includes(q);
  });
}

function sortTeams(teams) {
  const mode = safeText(sortSelect.value);
  const out = [...teams];

  if (mode === "wins") out.sort((a, b) => (Number(b.wins || 0) - Number(a.wins || 0)));
  else if (mode === "losses") out.sort((a, b) => (Number(b.losses || 0) - Number(a.losses || 0)));
  else out.sort((a, b) => computeDisplayName(a).localeCompare(computeDisplayName(b)));

  return out;
}

function render(teams) {
  teamsEl.innerHTML = "";

  if (!teams.length) {
    teamsEl.innerHTML = `<div class="muted">No teams found.</div>`;
    return;
  }

  for (const t of teams) {
    teamsEl.appendChild(createTeamCard(t));
  }
}

async function loadTeams() {
  teamsEl.innerHTML = `<div class="loading">Loading teams...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/teams`);
    const data = await res.json();

    if (!res.ok) {
      const msg = typeof data === "object" && data ? JSON.stringify(data) : safeText(data);
      throw new Error(msg || `HTTP ${res.status}`);
    }

    ALL_TEAMS = Array.isArray(data) ? data : [];
    updateView();
  } catch (err) {
    console.error(err);
    teamsEl.innerHTML = `
      <div class="error-message">
        <strong>Could not load teams</strong><br/>
        Make sure your backend is running on <code>${API_BASE}</code> and MySQL is configured.<br/>
        <div style="margin-top:8px;">Error: <code>${safeText(err.message)}</code></div>
      </div>
    `;
  }
}

function updateView() {
  const filtered = applyFilters(ALL_TEAMS);
  const sorted = sortTeams(filtered);
  render(sorted);
}

// UI events
searchInput.addEventListener("input", () => updateView());
confSelect.addEventListener("change", () => updateView());
sortSelect.addEventListener("change", () => updateView());

loadTeams();
