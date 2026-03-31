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

async function loadHomeQotdCard() {
    const card = document.getElementById('home-qotd-card');
    if (!card) return;

    const today = getLocalDateString();
    const qotdHref = `qotd.html?date=${encodeURIComponent(today)}`;

    try {
        const question = await fetchJson(`${API_URL}/api/qotd/${today}`);

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
    } catch (error) {
        console.error('Error loading home QOTD:', error);
        card.innerHTML = `
            <a href="${qotdHref}" class="home-qotd-link">
                <div class="home-qotd-label">QOTD</div>
                <h2>Question of the Day</h2>
                <p>Open the QOTD page to see today’s prompt.</p>
            </a>
        `;
        card.classList.remove('home-qotd-loading');
    }
}

async function fetchGames() {
    try {
        const response = await fetch(`${API_URL}/api/games/live`);
        const games = await response.json();
        const container = document.getElementById('games-container');

        if (!games || games.length === 0) {
            container.innerHTML = '<div class="no-games">No games scheduled for today</div>';
            return;
        }

        container.innerHTML = games.map((game) => createGameCard(game)).join('');
        await hydrateAlertButtons(games);
        await hydrateWatchlistButtons(games);
    } catch (error) {
        console.error('Error fetching games:', error);
        document.getElementById('games-container').innerHTML =
            '<div class="error">Failed to load games. Please try again.</div>';
    }
}

function createGameCard(game) {
    const homeTeam = game.home_team || {};
    const awayTeam = game.away_team || {};

    const homeAbbr = homeTeam.abbreviation || 'N/A';
    const awayAbbr = awayTeam.abbreviation || 'N/A';

    const homeLogo = teamLogos[homeAbbr] || '🏀';
    const awayLogo = teamLogos[awayAbbr] || '🏀';

    const statusClass = game.status?.toLowerCase() || 'upcoming';
    const statusText = game.status || 'Upcoming';
    const gameTime = game.game_time || 'TBD';

    const homeScore = game.home_score !== null && game.home_score !== undefined ? game.home_score : '-';
    const awayScore = game.away_score !== null && game.away_score !== undefined ? game.away_score : '-';

    const homeRecord = homeTeam.wins !== undefined ? `${homeTeam.wins}W - ${homeTeam.losses}L` : '';
    const awayRecord = awayTeam.wins !== undefined ? `${awayTeam.wins}W - ${awayTeam.losses}L` : '';

    const homeId = homeTeam.id || '';
    const awayId = awayTeam.id || '';
    const gameId = game.gameId || game.game_id || game.id || '';

    return `
        <div class="game-card" onclick="window.location.href='game-detail.html?id=${gameId}'" style="cursor: pointer;">
            <span class="game-status ${statusClass}">${statusText}</span>
            <button
                class="card-icon-btn game-watchlist-btn"
                type="button"
                data-game-id="${gameId}"
                onclick="toggleGameWatchlistFromCard(event, '${gameId}')"
                aria-label="Toggle game watchlist"
                title="Add game to watchlist"
            >
                <span>🔖</span>
            </button>
            <button
                class="card-icon-btn game-alert-btn"
                type="button"
                data-game-id="${gameId}"
                onclick="toggleGameAlertFromCard(event, '${gameId}')"
                aria-label="Toggle game alert"
                title="Save game alert"
            >
                <span>🔔</span>
            </button>
            <div class="game-time">${gameTime}</div>
            <div class="game-teams">
                <div class="team">
                    <a href="team-detail.html?id=${awayId}&from=live-games" onclick="event.stopPropagation()">
                        ${typeof awayLogo === 'string' && awayLogo.startsWith('http')
            ? `<img src="${awayLogo}" alt="${awayTeam.full_name}" class="team-logo" />`
            : `<div class="team-logo">${awayLogo}</div>`
        }
                        <div class="team-name">${awayTeam.full_name || 'Unknown'}</div>
                        ${awayRecord ? `<div class="team-record">${awayRecord}</div>` : ''}
                        <div class="team-score">${awayScore}</div>
                    </a>
                </div>
                <div class="vs">VS</div>
                <div class="team">
                    <a href="team-detail.html?id=${homeId}&from=live-games" onclick="event.stopPropagation()">
                        ${typeof homeLogo === 'string' && homeLogo.startsWith('http')
            ? `<img src="${homeLogo}" alt="${homeTeam.full_name}" class="team-logo" />`
            : `<div class="team-logo">${homeLogo}</div>`
        }
                        <div class="team-name">${homeTeam.full_name || 'Unknown'}</div>
                        ${homeRecord ? `<div class="team-record">${homeRecord}</div>` : ''}
                        <div class="team-score">${homeScore}</div>
                    </a>
                </div>
            </div>
        </div>
    `;
}

function manualRefresh() {
    document.getElementById('games-container').innerHTML =
        '<div class="loading"><div class="spinner"></div>Refreshing...</div>';
    fetchGames();
}

fetchGames();
setInterval(fetchGames, 30000);

loadHomeQotdCard();
