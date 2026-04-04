const API_BASE = 'http://localhost:8000';
const USER_ID_STORAGE_KEY = 'hoopwatch_user_id';

let allGames = [];
let activeFilter = 'all';
let searchTerm = '';
let watchlistedGameIds = new Set();
let alertGameIds = new Set();

const gameDatePicker = document.getElementById('gameDatePicker');

function readSavedUserId() {
  return localStorage.getItem(USER_ID_STORAGE_KEY) || '';
}

function getUserIdFromStorageOrPrompt() {
  const saved = Number(String(readSavedUserId()).trim());
  if (saved > 0) return saved;

  alert('Please log in to save game alerts and watchlist games.');
  window.location.href = 'login.html';
  return null;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data?.error || data?.message || `Request failed (${response.status})`);
  }

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

function normalizeGameId(game) {
  return String(game?.gameId || game?.game_id || game?.nba_game_id || '').trim();
}

function gameMatchesSearch(game, query) {
  if (!query) return true;

  const haystack = [
    game?.home_team?.full_name,
    game?.away_team?.full_name,
    game?.home_team?.abbreviation,
    game?.away_team?.abbreviation,
  ].join(' ').toLowerCase();

  return haystack.includes(query.toLowerCase());
}

function formatDateLabel(dateString) {
  if (!dateString) return 'Date TBD';
  const date = new Date(`${dateString}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateString;
  return date.toLocaleDateString(undefined, {
    weekday: 'long',
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


function getStatusForFilter(filterValue) {
  return filterValue === 'upcoming' ? 'scheduled' : filterValue;
}

function canOpenGameDetail(game) {
  return ['live', 'final'].includes(String(game?.status_key || ''));
}

function buildSeasonGameDetailHref(game) {
  const gameId = normalizeGameId(game);
  return `game-detail.html?id=${encodeURIComponent(gameId)}&from=season-games`;
}

function createSeasonGameCard(game) {
  const homeTeam = game.home_team || {};
  const awayTeam = game.away_team || {};
  const gameId = normalizeGameId(game);
  const watchlisted = watchlistedGameIds.has(gameId);
  const alerted = alertGameIds.has(gameId);
  const detailHref = canOpenGameDetail(game) ? buildSeasonGameDetailHref(game) : '';

  const statusKey = game.status_key === 'scheduled' ? 'upcoming' : (game.status_key || 'upcoming');
  const statusText = game.status_key === 'scheduled' ? 'Upcoming' : (game.status || 'Upcoming');
  const gameTime = game.game_time || 'TBD';

  const homeRecord = homeTeam.wins !== undefined ? `${homeTeam.wins}W - ${homeTeam.losses}L` : '';
  const awayRecord = awayTeam.wins !== undefined ? `${awayTeam.wins}W - ${awayTeam.losses}L` : '';

  const homeId = homeTeam.id || homeTeam.nba_team_id || '';
  const awayId = awayTeam.id || awayTeam.nba_team_id || '';
  const homeScore = game.home_score !== null && game.home_score !== undefined ? game.home_score : '-';
  const awayScore = game.away_score !== null && game.away_score !== undefined ? game.away_score : '-';

  return `
    <div class="game-card season-game-card ${detailHref ? 'clickable-game-card' : ''}" ${detailHref ? `data-detail-href="${escapeHtml(detailHref)}" role="link" tabindex="0"` : ''}>
      <span class="game-status ${escapeHtml(statusKey)}">${escapeHtml(statusText)}</span>
      <button
        class="card-icon-btn game-watchlist-btn ${watchlisted ? 'active' : ''}"
        type="button"
        data-game-id="${escapeHtml(gameId)}"
        data-action="watchlist"
        aria-label="Toggle game watchlist"
        title="${watchlisted ? 'Remove from watchlist' : 'Add game to watchlist'}"
      >
        <span>🔖</span>
      </button>
      <button
        class="card-icon-btn game-alert-btn ${alerted ? 'active' : ''}"
        type="button"
        data-game-id="${escapeHtml(gameId)}"
        data-action="alert"
        aria-label="Toggle game alert"
        title="${alerted ? 'Remove game alert' : 'Save game alert'}"
      >
        <span>🔔</span>
      </button>
      <div class="game-time">${escapeHtml(gameTime)}</div>
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
}

function getFilteredGames() {
  return allGames.filter((game) => {
    if (gameDatePicker && gameDatePicker.value) {
      const gameDate = String(game.game_date || '');
      if (gameDate !== gameDatePicker.value) return false;
    }

    const matchesSearch = gameMatchesSearch(game, searchTerm);
    if (!matchesSearch) return false;

    if (activeFilter === 'all') return true;
    if (activeFilter === 'completed') return game.status_key === 'final';
    return game.status_key === getStatusForFilter(activeFilter);
  });
}

function updateSummaryChips() {
  const total = allGames.length;
  const live = allGames.filter(game => game.status_key === 'live').length;
  const upcoming = allGames.filter(game => game.status_key === 'scheduled').length;
  const completed = allGames.filter(game => game.status_key === 'final').length;

  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  setText('all-count-chip', `All: ${total}`);
  setText('live-count-chip', `Live: ${live}`);
  setText('upcoming-count-chip', `Upcoming: ${upcoming}`);
  setText('completed-count-chip', `Completed: ${completed}`);
}

function groupGamesByDate(games) {
  const groups = new Map();
  games.forEach((game) => {
    const key = game.game_date || 'Date TBD';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(game);
  });
  return Array.from(groups.entries());
}

function buildResultMarkup(game) {
  const finalGame = game.status_key === 'final';
  const liveGame = game.status_key === 'live';
  const homeScore = game.home_score ?? '-';
  const awayScore = game.away_score ?? '-';

  if (finalGame) {
    const winner = game.winner_side === 'home' ? game.home_team?.abbreviation : game.away_team?.abbreviation;
    return `
      <div class="schedule-result-line"><strong>${escapeHtml(awayScore)} - ${escapeHtml(homeScore)}</strong></div>
      <div class="schedule-subtext">${escapeHtml(winner || 'Winner')} won</div>
    `;
  }

  if (liveGame) {
    return `
      <div class="schedule-result-line"><strong>${escapeHtml(awayScore)} - ${escapeHtml(homeScore)}</strong></div>
      <div class="schedule-subtext">${escapeHtml(game.game_time || 'Live')}</div>
    `;
  }

  return `
    <div class="schedule-result-line"><strong>${escapeHtml(game.game_time || 'TBD')}</strong></div>
    <div class="schedule-subtext">${escapeHtml(game.arena_name || 'Arena TBD')}</div>
  `;
}

function renderGameRow(game) {
  const gameId = normalizeGameId(game);
  const homeTeam = game.home_team || {};
  const awayTeam = game.away_team || {};
  const awayWon = game.winner_side === 'away';
  const homeWon = game.winner_side === 'home';
  const watchlisted = watchlistedGameIds.has(gameId);
  const alerted = alertGameIds.has(gameId);

  return `
    <article class="schedule-game-row">
      <div class="schedule-game-status ${escapeHtml(game.status_key || 'scheduled')}">${escapeHtml(game.status || 'Upcoming')}</div>

      <div class="schedule-game-main">
        <div class="schedule-matchup">
          <a class="schedule-team-link ${awayWon ? 'winner' : ''}" href="team-detail.html?id=${encodeURIComponent(awayTeam.id || awayTeam.nba_team_id || '')}&from=season-games">${escapeHtml(awayTeam.full_name || 'Away Team')}</a>
          <span class="schedule-at">@</span>
          <a class="schedule-team-link ${homeWon ? 'winner' : ''}" href="team-detail.html?id=${encodeURIComponent(homeTeam.id || homeTeam.nba_team_id || '')}&from=season-games">${escapeHtml(homeTeam.full_name || 'Home Team')}</a>
        </div>
        <div class="schedule-meta-row">
          <span>${escapeHtml(awayTeam.abbreviation || '')}</span>
          <span>•</span>
          <span>${escapeHtml(homeTeam.abbreviation || '')}</span>
          <span>•</span>
          <span>${escapeHtml(game.arena_name || 'Arena TBD')}</span>
        </div>
      </div>

      <div class="schedule-result-block">
        ${buildResultMarkup(game)}
      </div>

      <div class="schedule-actions">
        <button
          class="card-icon-btn compact-icon-btn ${watchlisted ? 'active' : ''}"
          type="button"
          data-game-id="${escapeHtml(gameId)}"
          data-action="watchlist"
          aria-label="Toggle game watchlist"
          title="${watchlisted ? 'Remove from watchlist' : 'Add game to watchlist'}"
        >🔖</button>
        <button
          class="card-icon-btn compact-icon-btn ${alerted ? 'active' : ''}"
          type="button"
          data-game-id="${escapeHtml(gameId)}"
          data-action="alert"
          aria-label="Toggle game alert"
          title="${alerted ? 'Remove game alert' : 'Save game alert'}"
        >🔔</button>
      </div>
    </article>
  `;
}

function renderSection(title, games) {
  if (!games.length) return '';

  const grouped = groupGamesByDate(games);
  const dateGroupsHtml = grouped.map(([dateKey, rows]) => `
    <div class="schedule-date-group">
      <div class="schedule-date-label">${escapeHtml(formatDateLabel(dateKey))}</div>
      <div class="games-container season-cards-grid">
        ${rows.map(createSeasonGameCard).join('')}
      </div>
    </div>
  `).join('');

  return `
    <section class="season-games-section">
      <div class="season-section-heading">
        <h2>${escapeHtml(title)}</h2>
        <span class="season-section-count">${games.length}</span>
      </div>
      ${dateGroupsHtml}
    </section>
  `;
}

function renderGames() {
  const container = document.getElementById('season-games-list');
  if (!container) return;

  const filteredGames = getFilteredGames();
  if (!filteredGames.length) {
    container.innerHTML = '<div class="no-games">No games matched that filter.</div>';
    return;
  }

  if (activeFilter === 'all') {
    const liveGames = filteredGames.filter(game => game.status_key === 'live');
    const upcomingGames = filteredGames.filter(game => game.status_key === 'scheduled');
    const completedGames = filteredGames.filter(game => game.status_key === 'final');

    container.innerHTML = [
      renderSection('Live Now', liveGames),
      renderSection('Games Left This Season', upcomingGames),
      renderSection('Completed Games', completedGames),
    ].join('');
  } else {
    const titleMap = {
      live: 'Live Games',
      upcoming: 'Upcoming Games',
      completed: 'Completed Games',
    };
    container.innerHTML = renderSection(titleMap[activeFilter] || 'Games', filteredGames);
  }
}

async function loadUserCollections() {
  const userId = Number(String(readSavedUserId()).trim());
  if (!userId) {
    watchlistedGameIds = new Set();
    alertGameIds = new Set();
    return;
  }

  try {
    const [watchlist, alerts] = await Promise.all([
      fetchJson(`${API_BASE}/api/users/${userId}/watchlist`).catch(() => []),
      fetchJson(`${API_BASE}/api/users/${userId}/alerts`).catch(() => []),
    ]);

    watchlistedGameIds = new Set((watchlist || []).map(item => String(item?.nba_game_id || item?.game_identifier || '')).filter(Boolean));
    alertGameIds = new Set((alerts || []).map(item => String(item?.nba_game_id || item?.game_identifier || '')).filter(Boolean));
  } catch (error) {
    console.error('Could not hydrate saved game collections:', error);
  }
}

async function toggleCollection(gameId, type, button) {
  const userId = getUserIdFromStorageOrPrompt();
  if (!userId || !gameId) return;

  const isWatchlist = type === 'watchlist';
  const isActive = isWatchlist ? watchlistedGameIds.has(gameId) : alertGameIds.has(gameId);
  const endpoint = isWatchlist ? 'watchlist' : 'alerts';

  try {
    button.disabled = true;

    if (isActive) {
      await fetchJson(`${API_BASE}/api/games/${gameId}/${endpoint}/${userId}`, { method: 'DELETE' });
      if (isWatchlist) watchlistedGameIds.delete(gameId);
      else alertGameIds.delete(gameId);
      showToast(isWatchlist ? 'Removed game from watchlist' : 'Game alert removed');
    } else {
      await fetchJson(`${API_BASE}/api/games/${gameId}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });
      if (isWatchlist) watchlistedGameIds.add(gameId);
      else alertGameIds.add(gameId);
      showToast(isWatchlist ? 'Added game to watchlist' : 'Game alert saved');
    }

    renderGames();
  } catch (error) {
    showToast(error.message || 'Could not update game setting.', 'error');
  } finally {
    button.disabled = false;
  }
}

async function loadSeasonGames() {
  const container = document.getElementById('season-games-list');

  try {
    container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading season games...</div>';
    const games = await fetchJson(`${API_BASE}/api/games/season`);
    allGames = Array.isArray(games) ? games : [];
    updateSummaryChips();
    await loadUserCollections();
    renderGames();
  } catch (error) {
    container.innerHTML = `<div class="error">Could not load season games: ${escapeHtml(error.message || 'Unknown error')}</div>`;
  }
}

document.addEventListener('click', (event) => {
  const filterButton = event.target.closest('.filter-pill[data-filter]');
  if (filterButton) {
    activeFilter = filterButton.dataset.filter;
    document.querySelectorAll('.filter-pill[data-filter]').forEach((button) => {
      button.classList.toggle('active', button === filterButton);
    });
    renderGames();
    return;
  }

  const actionButton = event.target.closest('[data-action][data-game-id]');
  if (actionButton) {
    const gameId = actionButton.dataset.gameId;
    const action = actionButton.dataset.action;
    toggleCollection(gameId, action, actionButton);
    return;
  }

  const detailCard = event.target.closest('.clickable-game-card[data-detail-href]');
  if (detailCard) {
    if (event.target.closest('a, button')) return;
    window.location.href = detailCard.dataset.detailHref;
  }
});

document.addEventListener('keydown', (event) => {
  const detailCard = event.target.closest('.clickable-game-card[data-detail-href]');
  if (!detailCard) return;
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  window.location.href = detailCard.dataset.detailHref;
});

document.getElementById('games-search-input')?.addEventListener('input', (event) => {
  searchTerm = event.target.value.trim();
  renderGames();
});

gameDatePicker?.addEventListener('change', () => {
  renderGames(); 
});

loadSeasonGames();
