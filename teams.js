const API_BASE = 'http://localhost:8000';
const USER_ID_STORAGE_KEY = 'hoopwatch_user_id';

const teamsEl = document.getElementById('teams');
const searchInput = document.getElementById('searchInput');
const confSelect = document.getElementById('confSelect');
const sortSelect = document.getElementById('sortSelect');

let ALL_TEAMS = [];
let FAVORITE_TEAM_IDS = new Set();

function nbaLogoUrl(teamId) {
  return `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`;
}

function safeText(value) {
  return (value ?? '').toString();
}

function readSavedUserId() {
  return localStorage.getItem(USER_ID_STORAGE_KEY) || '';
}

function getUserIdFromStorageOrPrompt() {
  const saved = Number(String(readSavedUserId()).trim());
  if (saved > 0) return saved;

  const entered = window.prompt('Enter your demo user ID to save favorite teams. Example: 2');
  const userId = Number(String(entered || '').trim());

  if (!userId || userId < 1) {
    alert('A valid user ID is required to save favorites.');
    return null;
  }

  localStorage.setItem(USER_ID_STORAGE_KEY, String(userId));
  return userId;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error || data?.message || `${res.status} ${res.statusText}`);
  return data;
}

function showToast(message, type = 'success', duration = 2800) {
  const container = document.querySelector('.toast-container') || (() => {
    const el = document.createElement('div');
    el.className = 'toast-container';
    document.body.appendChild(el);
    return el;
  })();

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(16px)';
  }, duration);

  setTimeout(() => {
    toast.remove();
    if (!container.children.length) container.remove();
  }, duration + 260);
}

function computeDisplayName(team) {
  const name = safeText(team.name);
  const city = safeText(team.city);
  if (!name) return city || 'Team';
  if (city && name.toLowerCase().startsWith(city.toLowerCase())) return name;
  return city ? `${city} ${name}` : name;
}

function isFavoriteTeam(team) {
  const teamId = Number(team.id || team.team_id || 0);
  return FAVORITE_TEAM_IDS.has(teamId);
}

function createTeamCard(team) {
  const wrapper = document.createElement('div');
  wrapper.className = 'team-card';

  const displayName = computeDisplayName(team);
  const abbr = safeText(team.abbreviation);
  const conf = safeText(team.conference);

  const wins = Number(team.wins || 0);
  const losses = Number(team.losses || 0);
  const pct = wins + losses > 0 ? (wins / (wins + losses)) : 0;
  const pctText = (pct * 100).toFixed(1);

  const nbaId = team.nba_team_id || team.nbaId || null;
  const fallbackLogo = nbaId ? nbaLogoUrl(nbaId) : '';
  const logoSrc = team.logo_url || fallbackLogo;
  const activeClass = isFavoriteTeam(team) ? 'active' : '';

  wrapper.innerHTML = `
    <button
      class="card-icon-btn team-favorite-btn ${activeClass}"
      type="button"
      data-team-id="${team.id}"
      onclick="toggleTeamFavoriteFromCard(event, '${team.id}')"
      aria-label="Toggle favorite team"
      title="Add team to favorites"
    >
      <span>${isFavoriteTeam(team) ? '★' : '☆'}</span>
    </button>
    <a href="team-detail.html?id=${team.id}">
      <div class="team-card-logo">
        <img src="${logoSrc}" alt="${displayName}" loading="lazy"
          style="width:100%;height:100%;object-fit:contain;"
          onerror="this.onerror=null;${nbaId ? `this.src='${nbaLogoUrl(nbaId)}';` : `this.style.display='none';`}" />
      </div>
      <div class="team-info">
        <h3>${displayName}</h3>
        <div class="team-city">${abbr}${conf ? ` • ${conf}` : ''}</div>
        <div class="team-record">${wins}-${losses}</div>
        <div class="team-win-rate">Win Rate: ${pctText}%</div>
      </div>
    </a>
  `;

  return wrapper;
}

function applyFilters(teams) {
  const q = safeText(searchInput.value).trim().toLowerCase();
  const conf = safeText(confSelect.value);

  return teams.filter((team) => {
    if (conf !== 'all' && safeText(team.conference) !== conf) return false;
    if (!q) return true;

    const haystack = [team.name, team.city, team.abbreviation, team.conference]
      .map((part) => safeText(part).toLowerCase())
      .join(' ');

    return haystack.includes(q);
  });
}

function sortTeams(teams) {
  const mode = safeText(sortSelect.value);
  const out = [...teams];

  if (mode === 'wins') out.sort((a, b) => (Number(b.wins || 0) - Number(a.wins || 0)));
  else if (mode === 'losses') out.sort((a, b) => (Number(b.losses || 0) - Number(a.losses || 0)));
  else out.sort((a, b) => computeDisplayName(a).localeCompare(computeDisplayName(b)));

  return out;
}

function render(teams) {
  teamsEl.innerHTML = '';

  if (!teams.length) {
    teamsEl.innerHTML = '<div class="muted">No teams found.</div>';
    return;
  }

  for (const team of teams) {
    teamsEl.appendChild(createTeamCard(team));
  }
}

async function loadFavoriteTeamIds() {
  FAVORITE_TEAM_IDS = new Set();

  const userId = Number(String(readSavedUserId()).trim());
  if (!userId) return;

  try {
    const favorites = await fetchJson(`${API_BASE}/api/users/${userId}/favorites`);
    FAVORITE_TEAM_IDS = new Set(
      (favorites || []).map((item) => Number(item.team_id || item.id || 0)).filter(Boolean)
    );
  } catch (error) {
    console.error('Could not load favorite teams:', error);
  }
}

async function toggleTeamFavoriteFromCard(event, teamId) {
  event.stopPropagation();
  event.preventDefault();

  const userId = getUserIdFromStorageOrPrompt();
  if (!userId) return;

  const numericTeamId = Number(teamId);
  const button = event.currentTarget;
  const isActive = FAVORITE_TEAM_IDS.has(numericTeamId);

  try {
    button.disabled = true;

    if (isActive) {
      await fetchJson(`${API_BASE}/api/users/${userId}/favorites/${numericTeamId}`, {
        method: 'DELETE'
      });
      FAVORITE_TEAM_IDS.delete(numericTeamId);
      showToast('Removed team from favorites', 'success');
    } else {
      await fetchJson(`${API_BASE}/api/users/${userId}/favorites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: numericTeamId })
      });
      FAVORITE_TEAM_IDS.add(numericTeamId);
      showToast('Added team to favorites', 'success');
    }

    updateView();
  } catch (error) {
    showToast(error.message || 'Could not update favorite team.', 'error');
  } finally {
    button.disabled = false;
  }
}

window.toggleTeamFavoriteFromCard = toggleTeamFavoriteFromCard;

async function loadTeams() {
  teamsEl.innerHTML = '<div class="loading">Loading teams...</div>';

  try {
    const res = await fetch(`${API_BASE}/api/teams`);
    const data = await res.json();

    if (!res.ok) {
      const message = typeof data === 'object' && data ? JSON.stringify(data) : safeText(data);
      throw new Error(message || `HTTP ${res.status}`);
    }

    ALL_TEAMS = Array.isArray(data) ? data : [];
    await loadFavoriteTeamIds();
    updateView();
  } catch (error) {
    console.error(error);
    teamsEl.innerHTML = `
      <div class="error-message">
        <strong>Could not load teams</strong><br/>
        Make sure your backend is running on <code>${API_BASE}</code> and MySQL is configured.<br/>
        <div style="margin-top:8px;">Error: <code>${safeText(error.message)}</code></div>
      </div>
    `;
  }
}

function updateView() {
  const filtered = applyFilters(ALL_TEAMS);
  const sorted = sortTeams(filtered);
  render(sorted);
}

searchInput.addEventListener('input', updateView);
confSelect.addEventListener('change', updateView);
sortSelect.addEventListener('change', updateView);

loadTeams();
