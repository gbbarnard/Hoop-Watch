// Team logos mapping
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

// Parse game clock from PT format to readable format
function parseGameClock(clock) {
    // Parse PT format like "PT01M28.00S" to "1:28"
    if (!clock || !clock.startsWith('PT')) return clock;
    
    const match = clock.match(/PT(\d+)M(\d+(?:\.\d+)?)S/);
    if (!match) return clock;
    
    const minutes = parseInt(match[1], 10);
    const seconds = Math.floor(parseFloat(match[2]));
    
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Get game ID from URL
const urlParams = new URLSearchParams(window.location.search);
const gameId = urlParams.get('id');

if (!gameId) {
    window.location.href = 'index.html';
}

async function fetchGameDetail() {
    try {
        const response = await fetch(`http://localhost:8000/api/games/${gameId}`);
        if (!response.ok) {
            throw new Error('Game not found');
        }
        const game = await response.json();
        displayGameDetail(game);
    } catch (error) {
        console.error('Error fetching game detail:', error);
        document.querySelector('.container').innerHTML = `
            <div class="error-message">
                <h2>Game data not available</h2>
                <p>This game may not have started yet or the data is unavailable.</p>
                <a href="index.html" class="btn">Back to Games</a>
            </div>
        `;
    }
}

function displayGameDetail(game) {
    const { homeTeam, awayTeam, gameStatus, gameStatusText, period, gameClock } = game;
    
    // Set team logos
    document.getElementById('away-logo').src = teamLogos[awayTeam.teamTricode] || '';
    document.getElementById('home-logo').src = teamLogos[homeTeam.teamTricode] || '';
    
    // Set team names and scores
    document.getElementById('away-team-name').textContent = `${awayTeam.teamCity} ${awayTeam.teamName}`;
    document.getElementById('home-team-name').textContent = `${homeTeam.teamCity} ${homeTeam.teamName}`;
    document.getElementById('away-score').textContent = awayTeam.score;
    document.getElementById('home-score').textContent = homeTeam.score;
    
    // Set game status
    const statusElement = document.getElementById('game-status');
    if (gameStatus === 2) {
        statusElement.innerHTML = '<span class="live-indicator"></span> LIVE';
        statusElement.classList.add('live');
        const formattedClock = parseGameClock(gameClock);
        document.getElementById('game-time').textContent = `Q${period} ${formattedClock}`;
    } else if (gameStatus === 3) {
        statusElement.textContent = 'FINAL';
        statusElement.classList.add('final');
    } else {
        statusElement.textContent = gameStatusText;
    }
    
    // Display quarter scores
    displayQuarterScores(homeTeam.periods, awayTeam.periods);
    
    // Display team stats
    displayTeamStats(game.homeTeam.statistics, game.awayTeam.statistics);
    
    // Display box scores
    displayBoxScore('away', awayTeam);
    displayBoxScore('home', homeTeam);
}

function displayQuarterScores(homePeriods, awayPeriods) {
    const container = document.getElementById('quarter-scores');
    
    if (!homePeriods || !awayPeriods || homePeriods.length === 0) {
        container.style.display = 'none';
        return;
    }
    
    let html = '<table class="quarter-table"><thead><tr><th>TEAM</th>';
    
    // Add period headers
    homePeriods.forEach((period, index) => {
        html += `<th>Q${index + 1}</th>`;
    });
    html += '<th>T</th></tr></thead><tbody>';
    
    // Away team row
    html += '<tr><td>Away</td>';
    let awayTotal = 0;
    awayPeriods.forEach(period => {
        const score = period.score || 0;
        awayTotal += score;
        html += `<td>${score}</td>`;
    });
    html += `<td><strong>${awayTotal}</strong></td></tr>`;
    
    // Home team row
    html += '<tr><td>Home</td>';
    let homeTotal = 0;
    homePeriods.forEach(period => {
        const score = period.score || 0;
        homeTotal += score;
        html += `<td>${score}</td>`;
    });
    html += `<td><strong>${homeTotal}</strong></td></tr>`;
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

function displayTeamStats(homeStats, awayStats) {
    const container = document.getElementById('team-stats');
    
    if (!homeStats || !awayStats) {
        container.innerHTML = '<p>Team statistics not available</p>';
        return;
    }
    
    const stats = [
        { label: 'Field Goals', homeKey: 'fieldGoalsMade', awayKey: 'fieldGoalsMade', suffix: '' },
        { label: 'FG%', homeKey: 'fieldGoalsPercentage', awayKey: 'fieldGoalsPercentage', suffix: '%' },
        { label: '3-Pointers', homeKey: 'threePointersMade', awayKey: 'threePointersMade', suffix: '' },
        { label: '3P%', homeKey: 'threePointersPercentage', awayKey: 'threePointersPercentage', suffix: '%' },
        { label: 'Free Throws', homeKey: 'freeThrowsMade', awayKey: 'freeThrowsMade', suffix: '' },
        { label: 'FT%', homeKey: 'freeThrowsPercentage', awayKey: 'freeThrowsPercentage', suffix: '%' },
        { label: 'Rebounds', homeKey: 'reboundsTotal', awayKey: 'reboundsTotal', suffix: '' },
        { label: 'Assists', homeKey: 'assists', awayKey: 'assists', suffix: '' },
        { label: 'Steals', homeKey: 'steals', awayKey: 'steals', suffix: '' },
        { label: 'Blocks', homeKey: 'blocks', awayKey: 'blocks', suffix: '' },
        { label: 'Turnovers', homeKey: 'turnovers', awayKey: 'turnovers', suffix: '' },
        { label: 'Points in Paint', homeKey: 'pointsInThePaint', awayKey: 'pointsInThePaint', suffix: '' },
        { label: 'Fast Break Points', homeKey: 'pointsFastBreak', awayKey: 'pointsFastBreak', suffix: '' },
        { label: 'Bench Points', homeKey: 'benchPoints', awayKey: 'benchPoints', suffix: '' }
    ];
    
    let html = '';
    stats.forEach(stat => {
        const homeValue = homeStats[stat.homeKey] || 0;
        const awayValue = awayStats[stat.awayKey] || 0;
        const homeHighlight = homeValue > awayValue ? ' highlight' : '';
        const awayHighlight = awayValue > homeValue ? ' highlight' : '';
        
        html += `
            <div class="stat-row">
                <div class="stat-value away${awayHighlight}">${awayValue}${stat.suffix}</div>
                <div class="stat-label">${stat.label}</div>
                <div class="stat-value home${homeHighlight}">${homeValue}${stat.suffix}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function displayBoxScore(team, teamData) {
    const tableId = team === 'away' ? 'away-boxscore' : 'home-boxscore';
    const titleId = team === 'away' ? 'away-team-boxscore-title' : 'home-team-boxscore-title';
    
    document.getElementById(titleId).textContent = `${teamData.teamCity} ${teamData.teamName} - Box Score`;
    
    const table = document.getElementById(tableId);
    
    if (!teamData.players || teamData.players.length === 0) {
        table.innerHTML = '<tr><td colspan="14">No player data available</td></tr>';
        return;
    }
    
    // Sort players: starters first, then bench
    const starters = teamData.players.filter(p => p.starter === '1');
    const bench = teamData.players.filter(p => p.starter !== '1');
    
    let html = `
        <thead>
            <tr>
                <th>PLAYER</th>
                <th>MIN</th>
                <th>PTS</th>
                <th>REB</th>
                <th>AST</th>
                <th>FG</th>
                <th>FG%</th>
                <th>3P</th>
                <th>3P%</th>
                <th>FT</th>
                <th>FT%</th>
                <th>STL</th>
                <th>BLK</th>
                <th>+/-</th>
            </tr>
        </thead>
        <tbody>
    `;
    
    // Add starters
    starters.forEach(player => {
        html += createPlayerRow(player);
    });
    
    // Add bench header
    if (bench.length > 0) {
        html += '<tr class="bench-header"><td colspan="14">BENCH</td></tr>';
        bench.forEach(player => {
            html += createPlayerRow(player);
        });
    }
    
    html += '</tbody>';
    table.innerHTML = html;
}

function createPlayerRow(player) {
    const plusMinus = player.plusMinusPoints || 0;
    const plusMinusClass = plusMinus > 0 ? 'positive' : plusMinus < 0 ? 'negative' : '';
    const plusMinusText = plusMinus > 0 ? `+${plusMinus}` : plusMinus;
    
    return `
        <tr>
            <td class="player-name">
                <span class="jersey-number">#${player.jerseyNum}</span>
                ${player.name} - ${player.position}
            </td>
            <td>${player.minutes || '0:00'}</td>
            <td>${player.points || 0}</td>
            <td>${player.reboundsTotal || 0}</td>
            <td>${player.assists || 0}</td>
            <td>${player.fieldGoalsMade || 0}-${player.fieldGoalsAttempted || 0}</td>
            <td>${player.fieldGoalsPercentage || '0.0'}%</td>
            <td>${player.threePointersMade || 0}-${player.threePointersAttempted || 0}</td>
            <td>${player.threePointersPercentage || '0.0'}%</td>
            <td>${player.freeThrowsMade || 0}-${player.freeThrowsAttempted || 0}</td>
            <td>${player.freeThrowsPercentage || '0.0'}%</td>
            <td>${player.steals || 0}</td>
            <td>${player.blocks || 0}</td>
            <td class="${plusMinusClass}">${plusMinusText}</td>
        </tr>
    `;
}

// Initial fetch
fetchGameDetail();

// Auto-refresh every 10 seconds for live games
setInterval(fetchGameDetail, 10000);
