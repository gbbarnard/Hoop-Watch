const API_URL = 'http://127.0.0.1:5000';



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
    
    return `
        <div class="game-card" onclick="window.location.href='game-detail.html?id=${gameId}'" style="cursor: pointer;">
            <span class="game-status ${statusClass}">${statusText}</span>
            <div class="game-time">${gameTime}</div>
            <div class="game-teams">
                <div class="team">
                    <a href="team-detail.html?id=${awayId}" onclick="event.stopPropagation()">
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
                    <a href="team-detail.html?id=${homeId}" onclick="event.stopPropagation()">
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
