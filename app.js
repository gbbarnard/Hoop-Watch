const API_URL = 'http://localhost:8000';
const USER_ID_STORAGE_KEY = 'hoopwatch_user_id';

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getLocalDateString() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

const teamLogos = {
    'ATL': 'https://cdn.nba.com/logos/nba/1610612737/primary/L/logo.svg',
    'BOS': 'https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg',
    'BKN': 'https://cdn.nba.com/logos/nba/1610612751/primary/L/logo.svg',
    'CHA': 'https://cdn.nba.com/logos/nba/1610612766/primary/L/logo.svg',
    'CHI': 'https://cdn.nba.com/logos/nba/1610612741/primary/L/logo.svg',
    'CLE': 'https://cdn.nba.com/logos/nba/1610612739/primary/L/logo.svg',
    'DAL': 'https://cdn.nba.com/logos/nba/1610612742/primary/L/logo.svg',
    'DEN': 'https://cdn.nba.com/logos/nba/1610612743/primary/L/logo.svg',
    'DET': 'https://cdn.nba.com/logos/nba/1610612765/primary/L/logo.svg',
    'GSW': 'https://cdn.nba.com/logos/nba/1610612744/primary/L/logo.svg',
    'HOU': 'https://cdn.nba.com/logos/nba/1610612745/primary/L/logo.svg',
    'IND': 'https://cdn.nba.com/logos/nba/1610612754/primary/L/logo.svg',
    'LAC': 'https://cdn.nba.com/logos/nba/1610612746/primary/L/logo.svg',
    'LAL': 'https://cdn.nba.com/logos/nba/1610612747/primary/L/logo.svg',
    'MEM': 'https://cdn.nba.com/logos/nba/1610612763/primary/L/logo.svg',
    'MIA': 'https://cdn.nba.com/logos/nba/1610612748/primary/L/logo.svg',
    'MIL': 'https://cdn.nba.com/logos/nba/1610612749/primary/L/logo.svg',
    'MIN': 'https://cdn.nba.com/logos/nba/1610612750/primary/L/logo.svg',
    'NOP': 'https://cdn.nba.com/logos/nba/1610612740/primary/L/logo.svg',
    'NYK': 'https://cdn.nba.com/logos/nba/1610612752/primary/L/logo.svg',
    'OKC': 'https://cdn.nba.com/logos/nba/1610612760/primary/L/logo.svg',
    'ORL': 'https://cdn.nba.com/logos/nba/1610612753/primary/L/logo.svg',
    'PHI': 'https://cdn.nba.com/logos/nba/1610612755/primary/L/logo.svg',
    'PHX': 'https://cdn.nba.com/logos/nba/1610612756/primary/L/logo.svg',
    'POR': 'https://cdn.nba.com/logos/nba/1610612757/primary/L/logo.svg',
    'SAC': 'https://cdn.nba.com/logos/nba/1610612758/primary/L/logo.svg',
    'SAS': 'https://cdn.nba.com/logos/nba/1610612759/primary/L/logo.svg',
    'TOR': 'https://cdn.nba.com/logos/nba/1610612761/primary/L/logo.svg',
    'UTA': 'https://cdn.nba.com/logos/nba/1610612762/primary/L/logo.svg',
    'WAS': 'https://cdn.nba.com/logos/nba/1610612764/primary/L/logo.svg'
};

function readSavedUserId() {
    return localStorage.getItem(USER_ID_STORAGE_KEY) || '';
}

function getUserIdFromStorageOrPrompt() {
    const saved = Number(String(readSavedUserId()).trim());
    if (saved > 0) return saved;

    alert('Please log in to save game alerts and watchlisted games.');
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

function updateAlertButtonState(button, isActive) {
    if (!button) return;
    button.classList.toggle('active', Boolean(isActive));
    button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    button.title = isActive ? 'Remove game alert' : 'Save game alert';
}

function updateWatchlistButtonState(button, isActive) {
    if (!button) return;
    button.classList.toggle('active', Boolean(isActive));
    button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    button.title = isActive ? 'Remove from watchlist' : 'Add game to watchlist';
}

async function hydrateWatchlistButtons(games) {
    const userId = Number(String(readSavedUserId()).trim());
    if (!userId) return;

    await Promise.all((games || []).map(async (game) => {
        const gameId = game.gameId || game.game_id || game.id || '';
        const button = document.querySelector(`.game-watchlist-btn[data-game-id="${CSS.escape(String(gameId))}"]`);
        if (!button || !gameId) return;

        try {
            const result = await fetchJson(`${API_URL}/api/games/${gameId}/watchlist/${userId}`);
            updateWatchlistButtonState(button, Boolean(result.is_watchlisted));
        } catch (error) {
            console.error(`Could not load watchlist state for game ${gameId}:`, error);
        }
    }));
}

async function toggleGameWatchlistFromCard(event, gameId) {
    event.stopPropagation();

    const button = event.currentTarget;
    const userId = getUserIdFromStorageOrPrompt();
    if (!userId || !gameId) return;

    const isActive = button.classList.contains('active');

    try {
        button.disabled = true;

        if (isActive) {
            await fetchJson(`${API_URL}/api/games/${gameId}/watchlist/${userId}`, {
                method: 'DELETE'
            });
            updateWatchlistButtonState(button, false);
            showToast('Removed game from watchlist', 'success');
        } else {
            await fetchJson(`${API_URL}/api/games/${gameId}/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });
            updateWatchlistButtonState(button, true);
            showToast('Added game to watchlist', 'success');
        }
    } catch (error) {
        showToast(error.message || 'Could not update watchlist.', 'error');
    } finally {
        button.disabled = false;
    }
}

window.toggleGameWatchlistFromCard = toggleGameWatchlistFromCard;

async function hydrateAlertButtons(games) {
    const userId = Number(String(readSavedUserId()).trim());
    if (!userId) return;

    await Promise.all((games || []).map(async (game) => {
        const gameId = game.gameId || game.game_id || game.id || '';
        const button = document.querySelector(`.game-alert-btn[data-game-id="${CSS.escape(String(gameId))}"]`);
        if (!button || !gameId) return;

        try {
            const result = await fetchJson(`${API_URL}/api/games/${gameId}/alerts/${userId}`);
            updateAlertButtonState(button, Boolean(result.has_alert));
        } catch (error) {
            console.error(`Could not load alert state for game ${gameId}:`, error);
        }
    }));
}

async function toggleGameAlertFromCard(event, gameId) {
    event.stopPropagation();

    const button = event.currentTarget;
    const userId = getUserIdFromStorageOrPrompt();
    if (!userId || !gameId) return;

    const isActive = button.classList.contains('active');

    try {
        button.disabled = true;

        if (isActive) {
            await fetchJson(`${API_URL}/api/games/${gameId}/alerts/${userId}`, {
                method: 'DELETE'
            });
            updateAlertButtonState(button, false);
            showToast('Game alert removed', 'success');
        } else {
            await fetchJson(`${API_URL}/api/games/${gameId}/alerts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });
            updateAlertButtonState(button, true);
            showToast('Game alert saved', 'success');
        }
    } catch (error) {
        showToast(error.message || 'Could not update game alert.', 'error');
    } finally {
        button.disabled = false;
    }
}

window.toggleGameAlertFromCard = toggleGameAlertFromCard;

function normalizeGameId(game) {
    return String(game?.gameId || game?.game_id || game?.nba_game_id || game?.id || '').trim();
}

function canOpenGameDetail(game) {
    return ['live', 'final'].includes(String(game?.status_key || '').trim().toLowerCase());
}

function buildHomeGameDetailHref(game) {
    const gameId = normalizeGameId(game);
    return gameId ? `game-detail.html?id=${encodeURIComponent(gameId)}&from=home` : '';
}

function formatTipoffTime(startTime) {
    const value = String(startTime || '').trim();
    if (!value) return '';

    const match = value.match(/^(\d{1,2}):(\d{2})(?::\d{2})?$/);
    if (!match) return value;

    let hours = Number(match[1]);
    const minutes = match[2];
    const suffix = hours >= 12 ? 'pm' : 'am';
    hours = hours % 12 || 12;
    return `${hours}:${minutes} ${suffix} ET`;
}

function getGameStatusBadge(game) {
    const rawKey = String(game?.status_key || '').trim().toLowerCase();
    const statusKey = rawKey === 'scheduled' ? 'upcoming' : (rawKey || 'upcoming');
    const statusText = statusKey === 'upcoming'
        ? 'Upcoming'
        : String(game?.status || (statusKey === 'live' ? 'Live' : 'Final'));
    return { statusKey, statusText };
}

function getGameTimeLabel(game) {
    const { statusKey } = getGameStatusBadge(game);
    if (statusKey === 'live') {
        return String(game?.game_time || game?.status || 'Live');
    }
    if (statusKey === 'final') {
        return 'Final';
    }
    return String(game?.game_time || formatTipoffTime(game?.start_time) || 'Upcoming');
}

function getTeamLogo(team) {
    if (team?.logo_url) return team.logo_url;
    if (team?.abbreviation && teamLogos[team.abbreviation]) return teamLogos[team.abbreviation];
    if (team?.nba_team_id) return `https://cdn.nba.com/logos/nba/${team.nba_team_id}/primary/L/logo.svg`;
    return '';
}

function createGameCard(game) {
    const homeTeam = game?.home_team || {};
    const awayTeam = game?.away_team || {};
    const gameId = normalizeGameId(game);
    const detailHref = canOpenGameDetail(game) ? buildHomeGameDetailHref(game) : '';
    const { statusKey, statusText } = getGameStatusBadge(game);
    const gameTime = getGameTimeLabel(game);

    const homeLabel = homeTeam?.full_name || `${homeTeam?.city || ''} ${homeTeam?.name || ''}`.trim() || homeTeam?.abbreviation || 'Home Team';
    const awayLabel = awayTeam?.full_name || `${awayTeam?.city || ''} ${awayTeam?.name || ''}`.trim() || awayTeam?.abbreviation || 'Away Team';
    const homeRecord = homeTeam?.wins !== undefined && homeTeam?.losses !== undefined ? `${homeTeam.wins}W - ${homeTeam.losses}L` : '';
    const awayRecord = awayTeam?.wins !== undefined && awayTeam?.losses !== undefined ? `${awayTeam.wins}W - ${awayTeam.losses}L` : '';
    const homeScore = game?.home_score !== null && game?.home_score !== undefined ? game.home_score : '-';
    const awayScore = game?.away_score !== null && game?.away_score !== undefined ? game.away_score : '-';
    const homeLogo = getTeamLogo(homeTeam);
    const awayLogo = getTeamLogo(awayTeam);

    return `
        <div class="game-card season-game-card ${detailHref ? 'clickable-game-card' : ''}" ${detailHref ? `data-detail-href="${escapeHtml(detailHref)}" role="link" tabindex="0"` : ''}>
            <span class="game-status ${escapeHtml(statusKey)}">${escapeHtml(statusText)}</span>
            <button
                class="card-icon-btn game-watchlist-btn"
                type="button"
                data-game-id="${escapeHtml(gameId)}"
                data-action="watchlist"
                aria-label="Toggle game watchlist"
                title="Add game to watchlist"
                onclick="toggleGameWatchlistFromCard(event, '${escapeHtml(gameId)}')"
            >
                <span>🔖</span>
            </button>
            <button
                class="card-icon-btn game-alert-btn"
                type="button"
                data-game-id="${escapeHtml(gameId)}"
                data-action="alert"
                aria-label="Toggle game alert"
                title="Save game alert"
                onclick="toggleGameAlertFromCard(event, '${escapeHtml(gameId)}')"
            >
                <span>🔔</span>
            </button>
            <div class="game-time">${escapeHtml(gameTime)}</div>
            <div class="game-teams">
                <div class="team">
                    ${awayLogo ? `<img src="${escapeHtml(awayLogo)}" alt="${escapeHtml(awayLabel)}" class="team-logo" />` : '<div class="team-logo">🏀</div>'}
                    <div class="team-name">${escapeHtml(awayLabel)}</div>
                    ${awayRecord ? `<div class="team-record">${escapeHtml(awayRecord)}</div>` : ''}
                    <div class="team-score">${escapeHtml(awayScore)}</div>
                </div>
                <div class="vs">VS</div>
                <div class="team">
                    ${homeLogo ? `<img src="${escapeHtml(homeLogo)}" alt="${escapeHtml(homeLabel)}" class="team-logo" />` : '<div class="team-logo">🏀</div>'}
                    <div class="team-name">${escapeHtml(homeLabel)}</div>
                    ${homeRecord ? `<div class="team-record">${escapeHtml(homeRecord)}</div>` : ''}
                    <div class="team-score">${escapeHtml(homeScore)}</div>
                </div>
            </div>
        </div>
    `;
}

function normalizeTeamDisplayName(team) {
    const rawName = String(team?.name || '').trim();
    const city = String(team?.city || '').trim();
    if (!rawName) return city || (team?.abbreviation || 'Team');
    if (!city) return rawName;
    return rawName.toLowerCase().startsWith(city.toLowerCase()) ? rawName : `${city} ${rawName}`.trim();
}

document.addEventListener('click', (event) => {
    const detailCard = event.target.closest('.clickable-game-card[data-detail-href]');
    if (!detailCard) return;
    if (event.target.closest('button')) return;
    const href = detailCard.getAttribute('data-detail-href');
    if (href) {
        window.location.href = href;
    }
});

document.addEventListener('keydown', (event) => {
    const detailCard = event.target.closest('.clickable-game-card[data-detail-href]');
    if (!detailCard) return;
    if (!['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    const href = detailCard.getAttribute('data-detail-href');
    if (href) {
        window.location.href = href;
    }
});

function renderHomeQotdCard(question, dateString) {
    const card = document.getElementById('home-qotd-card');
    if (!card) return;

    const qotdHref = `qotd.html?date=${encodeURIComponent(dateString)}`;

    if (!question || !question.question_id) {
        card.innerHTML = `
            <a href="${qotdHref}" class="home-qotd-link">
                <div class="home-qotd-label">QOTD</div>
                <h2>No question posted yet</h2>
                <p>Open the QOTD page to check again later.</p>
            </a>
        `;
        card.classList.remove('home-qotd-loading');
        return;
    }

    card.innerHTML = `
        <a href="${qotdHref}" class="home-qotd-link">
            <div class="home-qotd-label">QOTD</div>
            <h2>${escapeHtml(question.question_text)}</h2>
            <p>Click here to answer today’s question.</p>
        </a>
    `;
    card.classList.remove('home-qotd-loading');
}

function renderFactOfTheDay(factText) {
    const card = document.getElementById('fact-of-the-day-card');
    if (!card) return;

    card.innerHTML = `
        <div class="home-section-label">Fact of the Day</div>
        <p>${escapeHtml(factText || 'No fact has been posted yet for today.')}</p>
    `;
}

function renderFeaturedGame(featuredGame, source = 'auto') {
    const container = document.getElementById('featured-game-container');
    if (!container) return;

    if (!featuredGame) {
        container.innerHTML = '<div class="no-games">No featured game available right now.</div>';
        return;
    }

    const sourceText = source === 'admin'
        ? 'Picked by admin'
        : 'Auto-picked from today’s games';

    container.innerHTML = `
        <div class="featured-game-shell">
            <div class="featured-game-note">${escapeHtml(sourceText)}</div>
            ${createGameCard(featuredGame)}
        </div>
    `;
}

function createTeamWatchCard(team) {
    const teamId = team.team_id || team.id || '';
    const abbreviation = team.abbreviation || '';
    const logo = team.logo_url || teamLogos[abbreviation] || '🏀';
    const fullName = normalizeTeamDisplayName(team);
    const record = team.wins !== undefined && team.losses !== undefined
        ? `${team.wins}W - ${team.losses}L`
        : '';

    return `
        <a class="team-watch-card" href="team-detail.html?id=${encodeURIComponent(teamId)}">
            <div class="team-watch-card-top">
                ${typeof logo === 'string' && logo.startsWith('http')
                    ? `<img src="${escapeHtml(logo)}" alt="${escapeHtml(fullName)}" class="team-watch-logo" />`
                    : `<div class="team-watch-logo">${logo}</div>`
                }
                <div>
                    <div class="team-watch-name">${escapeHtml(fullName)}</div>
                    <div class="team-watch-abbr">${escapeHtml(abbreviation)}</div>
                </div>
            </div>
            <div class="team-watch-record">${escapeHtml(record || 'Record unavailable')}</div>
        </a>
    `;
}

function renderTeamsToWatch(teams) {
    const container = document.getElementById('teams-to-watch-container');
    if (!container) return;

    if (!teams || !teams.length) {
        container.innerHTML = '<div class="no-games">No teams to watch picked for today.</div>';
        return;
    }

    container.innerHTML = teams.map((team) => createTeamWatchCard(team)).join('');
}

async function hydrateHomeActionButtons(featuredGame, otherGames) {
    const allGames = [];
    if (featuredGame) allGames.push(featuredGame);
    if (Array.isArray(otherGames)) allGames.push(...otherGames);
    await hydrateAlertButtons(allGames);
    await hydrateWatchlistButtons(allGames);
}

function renderOtherTodayGames(games) {
    const container = document.getElementById('games-container');
    if (!container) return;

    if (!games || !games.length) {
        container.innerHTML = '<div class="no-games">No other games left for today.</div>';
        return;
    }

    container.innerHTML = games.map((game) => createGameCard(game)).join('');
}

async function loadHomePage() {
    const today = getLocalDateString();

    try {
        const homeData = await fetchJson(`${API_URL}/api/home-content/${today}`);
        renderHomeQotdCard(homeData.qotd, today);
        renderFactOfTheDay(homeData.fact_text);
        renderFeaturedGame(homeData.featured_game, homeData.featured_game_source);
        renderTeamsToWatch(homeData.teams_to_watch || []);
        renderOtherTodayGames(homeData.other_today_games || []);

        try {
            await hydrateHomeActionButtons(homeData.featured_game, homeData.other_today_games || []);
        } catch (hydrateError) {
            console.error('Error hydrating home page action buttons:', hydrateError);
        }
    } catch (error) {
        console.error('Error loading home page content:', error);
        renderHomeQotdCard(null, today);
        renderFactOfTheDay('Could not load today’s fact.');

        const featuredContainer = document.getElementById('featured-game-container');
        if (featuredContainer) {
            featuredContainer.innerHTML = '<div class="error">Failed to load the featured game.</div>';
        }

        const teamsContainer = document.getElementById('teams-to-watch-container');
        if (teamsContainer) {
            teamsContainer.innerHTML = '<div class="error">Failed to load teams to watch.</div>';
        }

        const gamesContainer = document.getElementById('games-container');
        if (gamesContainer) {
            gamesContainer.innerHTML = '<div class="error">Failed to load today’s games. Please try again.</div>';
        }
    }
}

function manualRefresh() {
    const featuredContainer = document.getElementById('featured-game-container');
    const gamesContainer = document.getElementById('games-container');
    if (featuredContainer) {
        featuredContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Refreshing featured game...</div>';
    }
    if (gamesContainer) {
        gamesContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Refreshing today’s games...</div>';
    }
    loadHomePage();
}

loadHomePage();
setInterval(loadHomePage, 30000);
