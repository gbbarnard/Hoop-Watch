const API_URL = 'http://localhost:8000';
const ALERTS_KEY = 'hoopwatch.gameAlerts';

// NBA team logo URLs from official sources
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

async function fetchGames() {
    try {
        const response = await fetch(`${API_URL}/api/games/live`);
        const games = await response.json();
        
        const container = document.getElementById('games-container');
        
        if (!games || games.length === 0) {
            container.innerHTML = '<div class="no-games">No games scheduled for today</div>';
            return;
        }
        
        container.innerHTML = games.map(game => createGameCard(game)).join('');
    } catch (error) {
        console.error('Error fetching games:', error);
        document.getElementById('games-container').innerHTML = 
            '<div class="error">Failed to load games. Please try again.</div>';
    }
}

function readJsonStorage(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        if (!raw) return fallback;
        const parsed = JSON.parse(raw);
        return parsed ?? fallback;
    } catch (error) {
        console.error(`Storage read error for ${key}:`, error);
        return fallback;
    }
}

function writeJsonStorage(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
}

function showToast(message) {
    const existing = document.querySelector('.toast-message');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast-message';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 2200);
}

function getAllAlerts() {
    const alerts = readJsonStorage(ALERTS_KEY, []);
    return Array.isArray(alerts) ? alerts : [];
}

function hasGameAlert(gameId) {
    return getAllAlerts().some((a) => String(a.gameId) === String(gameId));
}

function toggleGameAlert(event, gameId) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const all = getAllAlerts();
    const exists = all.some((a) => String(a.gameId) === String(gameId));
    const next = exists
        ? all.filter((a) => String(a.gameId) !== String(gameId))
        : [
            ...all,
            {
                id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
                gameId: String(gameId),
                leadMinutes: 10,
                createdAt: new Date().toISOString()
            }
        ];

    writeJsonStorage(ALERTS_KEY, next);

    // Update the clicked bell immediately so it feels like the team star toggle.
    const btn = event?.currentTarget;
    const nextActive = !exists;
    if (btn && typeof btn.classList !== 'undefined') {
        btn.classList.toggle('active', nextActive);
        btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
        const nextTitle = nextActive ? 'Remove game alert' : 'Set game alert';
        btn.setAttribute('title', nextTitle);
        btn.setAttribute('aria-label', nextTitle);
    }

    showToast(nextActive ? 'Alerts added' : 'Alerts removed');
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
    
    // Get game ID for navigation to game detail page
    const gameId = game.gameId || game.game_id || game.id || '';
    const alertActive = hasGameAlert(gameId);
    const alertTitle = alertActive ? 'Remove game alert' : 'Set game alert';
    
    return `
        <div class="game-card" onclick="window.location.href='game-detail.html?id=${gameId}'" style="cursor: pointer;">
            <button class="game-alert-btn ${alertActive ? 'active' : ''}" onclick="toggleGameAlert(event, '${gameId}');" title="${alertTitle}" aria-label="${alertTitle}" aria-pressed="${alertActive ? 'true' : 'false'}">
                <svg class="game-alert-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path d="M12 3a5 5 0 0 0-5 5v3.1c0 .95-.34 1.87-.95 2.6L4.8 15.2a1 1 0 0 0 .77 1.64h12.86a1 1 0 0 0 .77-1.64l-1.25-1.5a4 4 0 0 1-.95-2.6V8a5 5 0 0 0-5-5Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M9.5 18.2a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
            <span class="game-status ${statusClass}">${statusText}</span>
            <div class="game-time">${gameTime}</div>
            <div class="game-teams">
                <div class="team">
                    <a href="/team-detail.html?id=${awayId}" onclick="event.stopPropagation()">
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
                    <a href="/team-detail.html?id=${homeId}" onclick="event.stopPropagation()">
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

// Initial load
fetchGames();

// Auto refresh every 30 seconds
setInterval(fetchGames, 30000);

window.toggleGameAlert = toggleGameAlert;
