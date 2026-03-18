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
    document.getElementById('game-arena').textContent = game.arena_name ? `Arena: ${game.arena_name}` : 'Arena TBD';
    
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
        {
            label: 'Field Goals',
            homeValue: `${homeStats.fgm || 0}-${homeStats.fga || 0}`,
            awayValue: `${awayStats.fgm || 0}-${awayStats.fga || 0}`,
            homeCompare: homeStats.fgm || 0,
            awayCompare: awayStats.fgm || 0
        },
        {
            label: 'FG%',
            homeValue: `${((homeStats.fg_pct || 0) * 100).toFixed(1)}%`,
            awayValue: `${((awayStats.fg_pct || 0) * 100).toFixed(1)}%`,
            homeCompare: homeStats.fg_pct || 0,
            awayCompare: awayStats.fg_pct || 0
        },
        {
            label: '3-Pointers',
            homeValue: `${homeStats.fg3m || 0}-${homeStats.fg3a || 0}`,
            awayValue: `${awayStats.fg3m || 0}-${awayStats.fg3a || 0}`,
            homeCompare: homeStats.fg3m || 0,
            awayCompare: awayStats.fg3m || 0
        },
        {
            label: '3P%',
            homeValue: `${((homeStats.fg3_pct || 0) * 100).toFixed(1)}%`,
            awayValue: `${((awayStats.fg3_pct || 0) * 100).toFixed(1)}%`,
            homeCompare: homeStats.fg3_pct || 0,
            awayCompare: awayStats.fg3_pct || 0
        },
        {
            label: 'Free Throws',
            homeValue: `${homeStats.ftm || 0}-${homeStats.fta || 0}`,
            awayValue: `${awayStats.ftm || 0}-${awayStats.fta || 0}`,
            homeCompare: homeStats.ftm || 0,
            awayCompare: awayStats.ftm || 0
        },
        {
            label: 'FT%',
            homeValue: `${((homeStats.ft_pct || 0) * 100).toFixed(1)}%`,
            awayValue: `${((awayStats.ft_pct || 0) * 100).toFixed(1)}%`,
            homeCompare: homeStats.ft_pct || 0,
            awayCompare: awayStats.ft_pct || 0
        },
        {
            label: 'Rebounds',
            homeValue: homeStats.rebounds || 0,
            awayValue: awayStats.rebounds || 0,
            homeCompare: homeStats.rebounds || 0,
            awayCompare: awayStats.rebounds || 0
        },
        {
            label: 'Assists',
            homeValue: homeStats.assists || 0,
            awayValue: awayStats.assists || 0,
            homeCompare: homeStats.assists || 0,
            awayCompare: awayStats.assists || 0
        },
        {
            label: 'Steals',
            homeValue: homeStats.steals || 0,
            awayValue: awayStats.steals || 0,
            homeCompare: homeStats.steals || 0,
            awayCompare: awayStats.steals || 0
        },
        {
            label: 'Blocks',
            homeValue: homeStats.blocks || 0,
            awayValue: awayStats.blocks || 0,
            homeCompare: homeStats.blocks || 0,
            awayCompare: awayStats.blocks || 0
        },
        {
            label: 'Turnovers',
            homeValue: homeStats.turnovers || 0,
            awayValue: awayStats.turnovers || 0,
            homeCompare: homeStats.turnovers || 0,
            awayCompare: awayStats.turnovers || 0
        },
        {
            label: 'Points in Paint',
            homeValue: homeStats.pointsInPaint || 0,
            awayValue: awayStats.pointsInPaint || 0,
            homeCompare: homeStats.pointsInPaint || 0,
            awayCompare: awayStats.pointsInPaint || 0
        },
        {
            label: 'Fast Break Points',
            homeValue: homeStats.fastBreakPoints || 0,
            awayValue: awayStats.fastBreakPoints || 0,
            homeCompare: homeStats.fastBreakPoints || 0,
            awayCompare: awayStats.fastBreakPoints || 0
        },
        {
            label: 'Bench Points',
            homeValue: homeStats.benchPoints || 0,
            awayValue: awayStats.benchPoints || 0,
            homeCompare: homeStats.benchPoints || 0,
            awayCompare: awayStats.benchPoints || 0
        }
    ];

    let html = '';
    stats.forEach(stat => {
        const homeHighlight = stat.homeCompare > stat.awayCompare ? ' highlight' : '';
        const awayHighlight = stat.awayCompare > stat.homeCompare ? ' highlight' : '';

        html += `
            <div class="stat-row">
                <div class="stat-value away${awayHighlight}">${stat.awayValue}</div>
                <div class="stat-label">${stat.label}</div>
                <div class="stat-value home${homeHighlight}">${stat.homeValue}</div>
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
    const starters = teamData.players.filter(p => p.starter === true);
    const bench = teamData.players.filter(p => p.starter !== true);
    
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
    const plusMinus = player.plusMinus || 0;
    const plusMinusClass = plusMinus > 0 ? 'positive' : plusMinus < 0 ? 'negative' : '';
    const plusMinusText = plusMinus > 0 ? `+${plusMinus}` : plusMinus;

    const fgPct = typeof player.fg_pct === 'number'
        ? (player.fg_pct <= 1 ? (player.fg_pct * 100).toFixed(1) : Number(player.fg_pct).toFixed(1))
        : '0.0';

    const fg3Pct = typeof player.fg3_pct === 'number'
        ? (player.fg3_pct <= 1 ? (player.fg3_pct * 100).toFixed(1) : Number(player.fg3_pct).toFixed(1))
        : '0.0';

    const ftPct = typeof player.ft_pct === 'number'
        ? (player.ft_pct <= 1 ? (player.ft_pct * 100).toFixed(1) : Number(player.ft_pct).toFixed(1))
        : '0.0';

    return `
        <tr>
            <td class="player-name">
                <span class="jersey-number">#${player.jerseyNum || '-'}</span>
                ${player.name || ''}${player.position ? ` - ${player.position}` : ''}
            </td>
            <td>${player.minutes || '0:00'}</td>
            <td>${player.points || 0}</td>
            <td>${player.rebounds || 0}</td>
            <td>${player.assists || 0}</td>
            <td>${player.fgm || 0}-${player.fga || 0}</td>
            <td>${fgPct}%</td>
            <td>${player.fg3m || 0}-${player.fg3a || 0}</td>
            <td>${fg3Pct}%</td>
            <td>${player.ftm || 0}-${player.fta || 0}</td>
            <td>${ftPct}%</td>
            <td>${player.steals || 0}</td>
            <td>${player.blocks || 0}</td>
            <td class="${plusMinusClass}">${plusMinusText}</td>
        </tr>
    `;
}

// Initial fetch
fetchGameDetail();

// Auto-refresh every 10 seconds for live games
setInterval(fetchGameDetail, 50000);
