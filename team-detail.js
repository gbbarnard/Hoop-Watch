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

const favoriteTeamBtn = document.getElementById('favorite-team-btn');
const initialTeamTab = new URLSearchParams(window.location.search).get('tab') === 'games' ? 'games' : 'roster';

let currentTeam = null;
let isFavorite = false;
let teamGames = [];
let activeTeamGamesFilter = 'all';
const playerStatsCache = new Map();
const playerDirectory = new Map();

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
      showToast('Removed from favorite teams', 'success');
    } else {
      await fetchJson(`${API_BASE}/api/users/${userId}/favorites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: currentTeam.id })
      });
      isFavorite = true;
      showToast('Added to favorite teams', 'success');
    }
    updateFavoriteButton();
  } catch (error) {
    showToast(error.message || 'Could not update favorite team.', 'error');
  } finally {
    favoriteTeamBtn.disabled = false;
  }
}


function setActiveTab(tabName) {
  document.querySelectorAll('.team-tab-btn').forEach((button) => {
    const isActive = button.dataset.tab === tabName;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  document.querySelectorAll('.team-tab-panel').forEach((panel) => {
    const isActive = panel.id === `${tabName}-panel`;
    panel.classList.toggle('active', isActive);
  });
}

function formatTeamGameDate(dateString) {
  if (!dateString) return 'Date TBD';
  const date = new Date(`${dateString}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateString;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatPlayerBirthDate(dateString) {
  if (!dateString) return null;
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return dateString;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatPlayerInfoValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  return escapeHtml(value);
}

function buildPlayerInfoItems(player, payload) {
  const info = payload?.player_info || {};
  const merged = {
    jersey: player?.jersey ?? info.jersey,
    position: player?.position ?? info.position,
    height: player?.height ?? info.height,
    weight_lb: player?.weight_lb ?? info.weight_lb,
    age: player?.age ?? info.age,
    birth_date: player?.birth_date ?? info.birth_date,
    nba_player_id: player?.nba_player_id ?? info.nba_player_id,
  };

  return [
    { label: 'Jersey', value: merged.jersey ? `#${merged.jersey}` : null },
    { label: 'Position', value: merged.position },
    { label: 'Height', value: merged.height },
    { label: 'Weight', value: merged.weight_lb ? `${merged.weight_lb} lb` : null },
    { label: 'Age', value: merged.age },
    { label: 'Birth Date', value: formatPlayerBirthDate(merged.birth_date) },
    { label: 'NBA Player ID', value: merged.nba_player_id },
  ];
}

function formatPlayerStatValue(value, decimals = 1) {
  if (value === null || value === undefined || value === '') return '-';
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return escapeHtml(value);
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(decimals);
}

function renderPlayerStatsTable(payload, player = null) {
  const regularSeason = payload?.regular_season;
  const infoItems = buildPlayerInfoItems(player, payload);
  const infoHtml = infoItems.map((item) => `
    <div class="player-info-card">
      <div class="player-info-label">${escapeHtml(item.label)}</div>
      <div class="player-info-value">${formatPlayerInfoValue(item.value)}</div>
    </div>
  `).join('');

  const statsSection = regularSeason ? `
    <div class="player-stats-section-title">Season Stats</div>
    <div class="player-stats-scroll">
      <table class="player-stats-table">
        <thead>
          <tr>
            <th>Stats</th>
            <th>GP</th>
            <th>MIN</th>
            <th>FG%</th>
            <th>3P%</th>
            <th>FT%</th>
            <th>REB</th>
            <th>AST</th>
            <th>BLK</th>
            <th>STL</th>
            <th>PF</th>
            <th>TO</th>
            <th>PTS</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>${escapeHtml(regularSeason.season_label || 'Regular Season')}</td>
            <td>${formatPlayerStatValue(regularSeason.gp, 0)}</td>
            <td>${formatPlayerStatValue(regularSeason.min)}</td>
            <td>${formatPlayerStatValue(regularSeason.fg_pct)}</td>
            <td>${formatPlayerStatValue(regularSeason.fg3_pct)}</td>
            <td>${formatPlayerStatValue(regularSeason.ft_pct)}</td>
            <td>${formatPlayerStatValue(regularSeason.reb)}</td>
            <td>${formatPlayerStatValue(regularSeason.ast)}</td>
            <td>${formatPlayerStatValue(regularSeason.blk)}</td>
            <td>${formatPlayerStatValue(regularSeason.stl)}</td>
            <td>${formatPlayerStatValue(regularSeason.pf)}</td>
            <td>${formatPlayerStatValue(regularSeason.to)}</td>
            <td>${formatPlayerStatValue(regularSeason.pts)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  ` : `<div class="player-stats-empty">${escapeHtml(payload?.message || 'No stats available for this player yet.')}</div>`;

  const showMetaMessage = Boolean(regularSeason && payload?.message);
  const messageText = showMetaMessage ? escapeHtml(payload.message) : '';

  return `
    <div class="player-profile-panel">
      <div class="player-profile-header">
        <div>
          <div class="player-profile-name">${escapeHtml(player?.name || payload?.player_name || 'Player')}</div>
          <div class="player-profile-subtitle">Player information and regular season stats</div>
        </div>
      </div>
      <div class="player-info-grid">${infoHtml}</div>
      ${statsSection}
      ${messageText ? `<div class="player-stats-meta">${messageText}</div>` : ''}
    </div>
  `;
}

function closeRosterDropdowns(exceptRow = null) {
  document.querySelectorAll('.roster-player-row.expanded').forEach((row) => {
    if (exceptRow && row === exceptRow) return;
    row.classList.remove('expanded');
    row.setAttribute('aria-expanded', 'false');
    const statsRow = row.nextElementSibling;
    if (statsRow && statsRow.classList.contains('roster-player-stats-row')) {
      statsRow.classList.add('hidden');
    }
  });
}

async function toggleRosterPlayerStats(row) {
  if (!row) return;

  const statsRow = row.nextElementSibling;
  if (!statsRow || !statsRow.classList.contains('roster-player-stats-row')) return;

  const isOpen = row.classList.contains('expanded');
  closeRosterDropdowns(row);

  if (isOpen) {
    row.classList.remove('expanded');
    row.setAttribute('aria-expanded', 'false');
    statsRow.classList.add('hidden');
    return;
  }

  row.classList.add('expanded');
  row.setAttribute('aria-expanded', 'true');
  statsRow.classList.remove('hidden');

  const shell = statsRow.querySelector('.player-stats-shell');
  const playerId = row.dataset.playerId;
  if (!shell || !playerId) return;

  if (!playerStatsCache.has(playerId)) {
    shell.innerHTML = `<div class="player-stats-loading">Loading player stats…</div>`;
    try {
      const stats = await fetchJson(`${API_BASE}/api/players/${playerId}/stats`);
      playerStatsCache.set(playerId, stats);
    } catch (error) {
      shell.innerHTML = `<div class="player-stats-error">Could not load player stats. ${escapeHtml(error.message || '')}</div>`;
      return;
    }
  }

  shell.innerHTML = renderPlayerStatsTable(playerStatsCache.get(playerId), playerDirectory.get(String(playerId)) || null);
}

function canOpenTeamGameDetail(game) {
  return ['live', 'final'].includes(String(game?.status_key || ''));
}

function buildTeamGameDetailHref(game) {
  const gameId = encodeURIComponent(String(game?.game_id || game?.gameId || ''));
  const teamId = encodeURIComponent(String(currentTeam?.id || getTeamId() || ''));
  return `game-detail.html?id=${gameId}&from=team-games&teamId=${teamId}`;
}

function getTeamPerspective(game) {
  if (!currentTeam) return null;

  const homeTeam = game.home_team || {};
  const awayTeam = game.away_team || {};
  const currentIds = [String(currentTeam.id), String(currentTeam.nba_team_id)];
  const isHome = currentIds.includes(String(homeTeam.id)) || currentIds.includes(String(homeTeam.nba_team_id));
  const opponent = isHome ? awayTeam : homeTeam;
  const teamScore = isHome ? game.home_score : game.away_score;
  const opponentScore = isHome ? game.away_score : game.home_score;
  const won = game.status_key === 'final' && teamScore != null && opponentScore != null && Number(teamScore) > Number(opponentScore);
  const lost = game.status_key === 'final' && teamScore != null && opponentScore != null && Number(teamScore) < Number(opponentScore);

  return {
    isHome,
    opponent,
    teamScore,
    opponentScore,
    won,
    lost,
  };
}

function getFilteredTeamGames() {
  if (activeTeamGamesFilter === 'all') return teamGames;
  if (activeTeamGamesFilter === 'completed') return teamGames.filter((game) => game.status_key === 'final');
  const mappedFilter = activeTeamGamesFilter === 'upcoming' ? 'scheduled' : activeTeamGamesFilter;
  return teamGames.filter((game) => game.status_key === mappedFilter);
}

function renderTeamGames() {
  const container = document.getElementById('team-games-list');
  if (!container) return;

  const games = getFilteredTeamGames();
  if (!Array.isArray(games) || games.length === 0) {
    container.innerHTML = '<div class="no-games">No games matched that filter.</div>';
    return;
  }

  const cards = games.map((game) => {
    const view = getTeamPerspective(game);
    const homeTeam = game.home_team || {};
    const awayTeam = game.away_team || {};
    const statusKey = game.status_key === 'scheduled' ? 'upcoming' : (game.status_key || 'upcoming');
    const statusText = game.status_key === 'scheduled' ? 'Upcoming' : (game.status || 'Upcoming');
    const homeScore = game.home_score !== null && game.home_score !== undefined ? game.home_score : '-';
    const awayScore = game.away_score !== null && game.away_score !== undefined ? game.away_score : '-';
    const homeRecord = homeTeam.wins !== undefined ? `${homeTeam.wins}W - ${homeTeam.losses}L` : '';
    const awayRecord = awayTeam.wins !== undefined ? `${awayTeam.wins}W - ${awayTeam.losses}L` : '';
    const homeId = homeTeam.id || homeTeam.nba_team_id || '';
    const awayId = awayTeam.id || awayTeam.nba_team_id || '';
    const summary = view?.isHome ? `vs ${view?.opponent?.abbreviation || view?.opponent?.full_name || 'Opponent'}` : `@ ${view?.opponent?.abbreviation || view?.opponent?.full_name || 'Opponent'}`;

    const detailHref = canOpenTeamGameDetail(game) ? buildTeamGameDetailHref(game) : '';

    return `
      <div class="game-card season-game-card team-tab-game-card ${detailHref ? 'clickable-game-card' : ''}" ${detailHref ? `data-detail-href="${escapeHtml(detailHref)}" role="link" tabindex="0"` : ''}>
        <span class="game-status ${escapeHtml(statusKey)}">${escapeHtml(statusText)}</span>
        <div class="game-time">${escapeHtml(game.game_time || 'TBD')}</div>
        <div class="team-game-context">${escapeHtml(formatTeamGameDate(game.game_date))} • ${escapeHtml(summary)}</div>
        <div class="game-teams">
          <div class="team">
            <img src="${escapeHtml(awayTeam.logo_url || `https://cdn.nba.com/logos/nba/${awayTeam.nba_team_id}/primary/L/logo.svg`)}" alt="${escapeHtml(awayTeam.full_name || 'Away Team')}" class="team-logo" />
            <div class="team-name">${escapeHtml(awayTeam.full_name || 'Away Team')}</div>
            ${awayRecord ? `<div class="team-record">${escapeHtml(awayRecord)}</div>` : ''}
            <div class="team-score">${escapeHtml(awayScore)}</div>
          </div>
          <div class="vs">VS</div>
          <div class="team">
            <img src="${escapeHtml(homeTeam.logo_url || `https://cdn.nba.com/logos/nba/${homeTeam.nba_team_id}/primary/L/logo.svg`)}" alt="${escapeHtml(homeTeam.full_name || 'Home Team')}" class="team-logo" />
            <div class="team-name">${escapeHtml(homeTeam.full_name || 'Home Team')}</div>
            ${homeRecord ? `<div class="team-record">${escapeHtml(homeRecord)}</div>` : ''}
            <div class="team-score">${escapeHtml(homeScore)}</div>
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = `<div class="games-container team-games-card-grid">${cards}</div>`;
}

async function fetchTeamGames(teamId) {
  const container = document.getElementById('team-games-list');
  if (container) {
    container.innerHTML = '<div class="loading">Loading team games...</div>';
  }

  try {
    teamGames = await fetchJson(`${API_BASE}/api/teams/${teamId}/games`);
    renderTeamGames();
  } catch (error) {
    console.error('Team games error:', error);
    if (container) {
      container.innerHTML = `<div class="error">Could not load team games: ${error.message}</div>`;
    }
  }
}

async function fetchTeamRoster(teamId) {
  return fetchJson(`${API_BASE}/api/teams/${teamId}/roster`);
}

async function loadRosterForTeam(teamId, tbody) {
  try {
    const players = await fetchTeamRoster(teamId);
    displayRoster(players);
  } catch (rosterErr) {
    console.error('Roster error:', rosterErr);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Roster unavailable. Backend error: <code>${rosterErr.message}</code></td></tr>`;
    }
  }
}

async function loadTeamPageByInternalId(teamId, tbody) {
  const team = await fetchJson(`${API_BASE}/api/teams/${teamId}`);
  currentTeam = team;
  await displayTeamHeader(team);
  await refreshFavoriteStatus();
  await loadRosterForTeam(teamId, tbody);
  await fetchTeamGames(teamId);
}

async function resolveInternalTeamId(rawId) {
  const isLikelyNbaId = /^\d{9,}$/.test(String(rawId)) && Number(rawId) > 1600000000;
  if (!isLikelyNbaId) return rawId;

  const allTeams = await fetchJson(`${API_BASE}/api/teams`);
  const match = Array.isArray(allTeams)
    ? allTeams.find((team) => String(team.nba_team_id) === String(rawId))
    : null;

  return match?.id || null;
}

async function fetchTeamData() {
  const rawId = getTeamId();
  if (!rawId) {
    document.body.innerHTML = '<p>Team not found</p>';
    return;
  }

  const tbody = document.getElementById('roster-tbody');
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Loading roster…</td></tr>`;
  }

  try {
    await loadTeamPageByInternalId(rawId, tbody);
  } catch (error) {
    try {
      const resolvedInternalId = await resolveInternalTeamId(rawId);
      if (resolvedInternalId) {
        await loadTeamPageByInternalId(resolvedInternalId, tbody);
        return;
      }
    } catch (resolveError) {
      console.error('NBA id resolve failed:', resolveError);
    }

    console.error('Error fetching team data:', error);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Could not load team. Backend error: <code>${error.message}</code></td></tr>`;
    }
  }
}

function handleBackButton() {
  const params = new URLSearchParams(window.location.search);
  const from = params.get("from");

  const backLink = document.querySelector(".back-link");

  if (!backLink) return;

  if (from === "season-games") {
    backLink.href = "games.html";
  } else if (from === "live-games" || from === "games") {
    backLink.href = "index.html";
  } else {
    backLink.href = "teams.html";
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
  closeRosterDropdowns();
  playerDirectory.clear();

  if (!Array.isArray(players) || players.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">No roster returned.</td></tr>`;
    return;
  }

  players.forEach((p) => {
    const playerIdKey = String(p.id || '');
    if (playerIdKey) {
      playerDirectory.set(playerIdKey, p);
    }

    const row = document.createElement("tr");
    row.className = 'roster-player-row';

    const playerId = p.id || 0;
    if (playerId) row.dataset.playerId = String(playerId);
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    row.setAttribute('aria-expanded', 'false');
    const imgHtml = playerId
      ? `<img src="${p.headshot_url || headshotUrl(playerId)}" alt="${escapeHtml(p.name)}" style="width:48px;height:36px;object-fit:cover;border-radius:6px;" onerror="this.style.display='none'">`
      : "";

    row.innerHTML = `
      <td style="padding:10px 12px;">${imgHtml}</td>
      <td style="padding:10px 12px;">${escapeHtml(p.jersey ?? "-")}</td>
      <td style="padding:10px 12px; font-weight:600;">
        <div class="roster-player-name-cell">
          <span>${escapeHtml(p.name ?? "")}</span>
          <span class="roster-expand-indicator" aria-hidden="true">▾</span>
        </div>
      </td>
      <td style="padding:10px 12px;">${escapeHtml(p.position ?? "-")}</td>
      <td style="padding:10px 12px;">${escapeHtml(p.height ?? "-")}</td>
    `;
    tbody.appendChild(row);

    const statsRow = document.createElement('tr');
    statsRow.className = 'roster-player-stats-row hidden';
    statsRow.innerHTML = `
      <td colspan="5">
        <div class="player-stats-shell">
          <div class="player-stats-empty">Click this player to view player information and regular season stats.</div>
        </div>
      </td>
    `;
    tbody.appendChild(statsRow);
  });
}

if (favoriteTeamBtn) {
  favoriteTeamBtn.addEventListener('click', toggleFavoriteTeam);
}

document.addEventListener('click', (event) => {
  const tabButton = event.target.closest('.team-tab-btn[data-tab]');
  if (tabButton) {
    setActiveTab(tabButton.dataset.tab);
    return;
  }

  const filterButton = event.target.closest('.filter-pill[data-team-games-filter]');
  if (filterButton) {
    activeTeamGamesFilter = filterButton.dataset.teamGamesFilter;
    document.querySelectorAll('.filter-pill[data-team-games-filter]').forEach((button) => {
      button.classList.toggle('active', button === filterButton);
    });
    renderTeamGames();
    return;
  }

  const rosterRow = event.target.closest('.roster-player-row[data-player-id]');
  if (rosterRow) {
    toggleRosterPlayerStats(rosterRow);
    return;
  }

  const detailCard = event.target.closest('.clickable-game-card[data-detail-href]');
  if (detailCard) {
    if (event.target.closest('a, button')) return;
    window.location.href = detailCard.dataset.detailHref;
  }
});

document.addEventListener('keydown', (event) => {
  const rosterRow = event.target.closest('.roster-player-row[data-player-id]');
  if (rosterRow && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault();
    toggleRosterPlayerStats(rosterRow);
    return;
  }

  const detailCard = event.target.closest('.clickable-game-card[data-detail-href]');
  if (!detailCard) return;
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  window.location.href = detailCard.dataset.detailHref;
});

setActiveTab(initialTeamTab);
handleBackButton();
updateFavoriteButton();
fetchTeamData();
