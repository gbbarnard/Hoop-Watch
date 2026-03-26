const API_BASE = "http://localhost:8000";
const USER_ID_STORAGE_KEY = 'hoopwatch_user_id';

function logoUrl(teamId) {
  return `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`;
}
function headshotUrl(playerId) {
  return `https://cdn.nba.com/headshots/nba/latest/260x190/${playerId}.png`;
}

function getTeamId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

function readSavedUserId() {
  return localStorage.getItem(USER_ID_STORAGE_KEY) || '';
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error || data?.message || `${res.status} ${res.statusText}`);
  return data;
}

const favoriteTeamBtn = document.getElementById('favorite-team-btn');

let currentTeam = null;
let isFavorite = false;

function getFavoriteUserIdOrWarn() {
  let saved = String(readSavedUserId() || '').trim();

  if (!saved) {
    saved = String(prompt('Enter your demo user ID:') || '').trim();
  }

  const value = Number(saved);
  if (!value || value < 1) {
    alert('Enter a valid user ID first. Example: 2');
    return null;
  }

  localStorage.setItem(USER_ID_STORAGE_KEY, String(value));
  return value;
}

function updateFavoriteButton() {
  if (!favoriteTeamBtn) return;

  favoriteTeamBtn.textContent = isFavorite ? '★' : '☆';
  favoriteTeamBtn.classList.toggle('active', isFavorite);
  favoriteTeamBtn.title = isFavorite ? 'Remove from favorites' : 'Add to favorites';
  favoriteTeamBtn.setAttribute('aria-label', favoriteTeamBtn.title);
}

async function refreshFavoriteStatus() {
  if (!currentTeam) return;

  const userId = Number(String(readSavedUserId() || '').trim());
  if (!userId) {
    isFavorite = false;
    updateFavoriteButton();
    return;
  }

  try {
    const result = await fetchJson(`${API_BASE}/api/users/${userId}/favorites/${currentTeam.id}`);
    isFavorite = Boolean(result.is_favorite);
  } catch (error) {
    console.error('Could not load favorite status:', error);
    isFavorite = false;
  }

  updateFavoriteButton();
}

async function toggleFavoriteTeam() {
  if (!currentTeam) return;
  const userId = getFavoriteUserIdOrWarn();
  if (!userId) return;

  try {
    favoriteTeamBtn.disabled = true;
    if (isFavorite) {
      await fetchJson(`${API_BASE}/api/users/${userId}/favorites/${currentTeam.id}`, { method: 'DELETE' });
      isFavorite = false;
    } else {
      await fetchJson(`${API_BASE}/api/users/${userId}/favorites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: currentTeam.id })
      });
      isFavorite = true;
    }
    updateFavoriteButton();
  } catch (error) {
    alert(error.message || 'Could not update favorite team.');
  } finally {
    favoriteTeamBtn.disabled = false;
  }
}

async function fetchTeamData() {
  const rawId = getTeamId();
  if (!rawId) {
    document.body.innerHTML = "<p>Team not found</p>";
    return;
  }

  const isLikelyNbaId = /^\d{9,}$/.test(String(rawId)) && Number(rawId) > 1600000000;

  const tbody = document.getElementById("roster-tbody");
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Loading roster…</td></tr>`;
  }

  let internalId = rawId;
  try {
    const team = await fetchJson(`${API_BASE}/api/teams/${internalId}`);
    currentTeam = team;
    await displayTeamHeader(team);
    await refreshFavoriteStatus();

    try {
      const players = await fetchJson(`${API_BASE}/api/teams/${internalId}/players`);
      displayRoster(players);
    } catch (rosterErr) {
      console.error("Roster error:", rosterErr);
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Roster unavailable. Backend error: <code>${rosterErr.message}</code></td></tr>`;
      }
    }

  } catch (error) {
    if (isLikelyNbaId) {
      try {
        const allTeams = await fetchJson(`${API_BASE}/api/teams`);
        const match = Array.isArray(allTeams)
          ? allTeams.find(t => String(t.nba_team_id) === String(rawId))
          : null;

        if (match && match.id) {
          internalId = match.id;
          const team = await fetchJson(`${API_BASE}/api/teams/${internalId}`);
          currentTeam = team;
          await displayTeamHeader(team);
          await refreshFavoriteStatus();

          try {
            const players = await fetchJson(`${API_BASE}/api/teams/${internalId}/players`);
            displayRoster(players);
            return;
          } catch (rosterErr) {
            console.error("Roster error:", rosterErr);
            if (tbody) {
              tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Roster unavailable. Backend error: <code>${rosterErr.message}</code></td></tr>`;
            }
            return;
          }
        }
      } catch (e2) {
        console.error("NBA id resolve failed:", e2);
      }
    }

    console.error("Error fetching team data:", error);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Could not load team. Backend error: <code>${error.message}</code></td></tr>`;
    }
  }
}

async function loadFirstWorkingImage(urls) {
  for (const url of urls) {
    if (!url) continue;
    const ok = await new Promise((resolve) => {
      const test = new Image();
      try { test.referrerPolicy = "no-referrer"; } catch (e) { }
      test.onload = () => resolve(true);
      test.onerror = () => resolve(false);
      test.src = url;
    });
    if (ok) return url;
  }
  return null;
}

function buildLogoCandidates(team) {
  const nbaId = team.nba_team_id || team.nbaId || null;
  const abbr = team.abbreviation || team.abbrev || "";
  const candidates = [];

  if (team.logo_url) candidates.push(team.logo_url);

  if (nbaId) {
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/global/L/logo.svg`);
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/global/L/logo.png`);
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/primary/L/logo.svg`);
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/primary/L/logo.png`);
  }

  if (abbr) {
    candidates.push(`database/static/Logos/${abbr}.png`);
    candidates.push(`static/Logos/${abbr}.png`);
    candidates.push(`/static/Logos/${abbr}.png`);
  }

  return candidates;
}

async function displayTeamHeader(team) {
  const img = document.getElementById("team-logo-img");
  const fallback = document.getElementById("team-logo-fallback");

  const showImg = () => {
    img.style.display = "block";
    fallback.style.display = "none";
  };
  const showFallback = () => {
    img.style.display = "none";
    fallback.style.display = "inline";
  };

  const candidates = buildLogoCandidates(team);
  const chosen = await loadFirstWorkingImage(candidates);

  if (chosen) {
    img.onerror = () => showFallback();
    img.onload = () => showImg();
    img.src = chosen;
    if (img.complete && img.naturalWidth > 0) showImg();
    else showImg();
  } else {
    showFallback();
  }

  document.getElementById('team-arena').textContent = team.arena ? `Arena: ${team.arena}` : 'Arena: Arena TBD';
  document.getElementById("team-name").textContent = team.full_name || team.name || "Team";

  const wins = Number(team.wins || 0);
  const losses = Number(team.losses || 0);
  const winRate = wins + losses > 0 ? ((wins / (wins + losses)) * 100).toFixed(1) : "0.0";

  const teamRecordPill = document.getElementById('team-record-pill');
  const teamWinRatePill = document.getElementById('team-win-rate-pill');
  if (teamRecordPill) teamRecordPill.textContent = `${wins}W - ${losses}L`;
  if (teamWinRatePill) teamWinRatePill.textContent = `Win Rate: ${winRate}%`;
}

function displayRoster(players) {
  const tbody = document.getElementById("roster-tbody");
  tbody.innerHTML = "";

  if (!Array.isArray(players) || players.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">No roster returned.</td></tr>`;
    return;
  }

  players.forEach((p) => {
    const row = document.createElement("tr");

    const playerId = p.id || 0;
    const imgHtml = playerId
      ? `<img src="${p.headshot_url || headshotUrl(playerId)}" alt="${p.name}" style="width:48px;height:36px;object-fit:cover;border-radius:6px;" onerror="this.style.display='none'">`
      : "";

    row.innerHTML = `
      <td style="padding:10px 12px;">${imgHtml}</td>
      <td style="padding:10px 12px;">${p.jersey ?? "-"}</td>
      <td style="padding:10px 12px; font-weight:600;">${p.name ?? ""}</td>
      <td style="padding:10px 12px;">${p.position ?? "-"}</td>
      <td style="padding:10px 12px;">${p.height ?? "-"}</td>
    `;
    tbody.appendChild(row);
  });
}

favoriteTeamBtn.addEventListener('click', toggleFavoriteTeam);
updateFavoriteButton();
fetchTeamData();
