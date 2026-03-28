const API_BASE = 'http://localhost:8000';
const USER_ID_STORAGE_KEY = 'hoopwatch_user_id';
const DISPLAY_NAME_STORAGE_KEY = 'hoopwatch_display_name';

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

const urlParams = new URLSearchParams(window.location.search);
const gameId = urlParams.get('id');
const commentsList = document.getElementById('game-comments-list');
const postCommentBtn = document.getElementById('post-game-comment-btn');
const commentTextInput = document.getElementById('game-comment-text');
const commentDisplayNameInput = document.getElementById('comment-display-name');

let currentGame = null;
let commentsRefreshTimer = null;

function getBackLinkInfo() {
    const from = urlParams.get('from');
    const teamId = urlParams.get('teamId');

    if (from === 'season-games') {
        return { href: 'games.html', label: '← Back to Season Games' };
    }

    if (from === 'team-games' && teamId) {
        return { href: `team-detail.html?id=${encodeURIComponent(teamId)}&tab=games`, label: '← Back to Team Games' };
    }

    return { href: 'index.html', label: '← Back to Home' };
}

function applyBackLink() {
    const backLink = document.querySelector('.detail-back-link');
    if (!backLink) return;
    const info = getBackLinkInfo();
    backLink.href = info.href;
    backLink.textContent = info.label;
}

if (!gameId) {
    window.location.href = getBackLinkInfo().href;
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '\'': '&#39;',
        '"': '&quot;'
    }[char]));
}

function parseGameClock(clock) {
    if (!clock || !clock.startsWith('PT')) return clock;

    const match = clock.match(/PT(\d+)M(\d+(?:\.\d+)?)S/);
    if (!match) return clock;

    const minutes = parseInt(match[1], 10);
    const seconds = Math.floor(parseFloat(match[2]));

    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function readSavedUserId() {
    return localStorage.getItem(USER_ID_STORAGE_KEY) || '';
}

function readSavedDisplayName() {
    return localStorage.getItem(DISPLAY_NAME_STORAGE_KEY) || '';
}

function ensureUserId() {
    const saved = Number(String(readSavedUserId()).trim());
    if (saved > 0) return saved;

    alert('Please log in to post comments.');
    window.location.href = 'login.html';
    return null;
}

function persistDisplayName() {
    const value = String(commentDisplayNameInput.value || '').trim();
    if (value) localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, value);
    else localStorage.removeItem(DISPLAY_NAME_STORAGE_KEY);
}

function formatCommentDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const message = data?.error || data?.message || `Request failed (${response.status})`;
        throw new Error(message);
    }
    return data;
}

async function fetchGameDetail() {
    try {
        const game = await fetchJson(`${API_BASE}/api/games/${gameId}`);
        currentGame = game;
        displayGameDetail(game);
        await loadGameComments();
    } catch (error) {
        console.error('Error fetching game detail:', error);
        const backLink = getBackLinkInfo();
        document.querySelector('.container').innerHTML = `
            <div class="error-message">
                <h2>Game data not available</h2>
                <p>This game may not have started yet or the data is unavailable.</p>
                <a href="${backLink.href}" class="btn">${backLink.label.replace('← ', '')}</a>
            </div>
        `;
    }
}

function displayGameDetail(game) {
    const { homeTeam, awayTeam, gameStatus, gameStatusText, period, gameClock } = game;

    document.getElementById('away-logo').src = teamLogos[awayTeam.teamTricode] || '';
    document.getElementById('home-logo').src = teamLogos[homeTeam.teamTricode] || '';

    document.getElementById('away-team-name').textContent = `${awayTeam.teamCity} ${awayTeam.teamName}`;
    document.getElementById('home-team-name').textContent = `${homeTeam.teamCity} ${homeTeam.teamName}`;
    document.getElementById('away-score').textContent = awayTeam.score;
    document.getElementById('home-score').textContent = homeTeam.score;
    document.getElementById('game-arena').textContent = game.arena_name ? `Arena: ${game.arena_name}` : 'Arena TBD';

    const statusElement = document.getElementById('game-status');
    statusElement.classList.remove('live', 'final');

    if (gameStatus === 2) {
        statusElement.innerHTML = '<span class="live-indicator"></span> LIVE';
        statusElement.classList.add('live');
        const formattedClock = parseGameClock(gameClock);
        document.getElementById('game-time').textContent = `Q${period} ${formattedClock}`;
    } else if (gameStatus === 3) {
        statusElement.textContent = 'FINAL';
        statusElement.classList.add('final');
        document.getElementById('game-time').textContent = gameStatusText || '';
    } else {
        statusElement.textContent = gameStatusText;
        document.getElementById('game-time').textContent = gameStatusText || '';
    }

    displayQuarterScores(homeTeam.periods, awayTeam.periods);
    displayTeamStats(game.homeTeam.statistics, game.awayTeam.statistics);
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

    homePeriods.forEach((period, index) => {
        html += `<th>Q${index + 1}</th>`;
    });
    html += '<th>T</th></tr></thead><tbody>';

    html += '<tr><td>Away</td>';
    let awayTotal = 0;
    awayPeriods.forEach((period) => {
        const score = period.score || 0;
        awayTotal += score;
        html += `<td>${score}</td>`;
    });
    html += `<td><strong>${awayTotal}</strong></td></tr>`;

    html += '<tr><td>Home</td>';
    let homeTotal = 0;
    homePeriods.forEach((period) => {
        const score = period.score || 0;
        homeTotal += score;
        html += `<td>${score}</td>`;
    });
    html += `<td><strong>${homeTotal}</strong></td></tr>`;

    html += '</tbody></table>';
    container.innerHTML = html;
    container.style.display = 'block';
}

function getStatValue(source, keys, fallback = 0) {
    for (const key of keys) {
        if (source && source[key] !== undefined && source[key] !== null && source[key] !== '') {
            return source[key];
        }
    }
    return fallback;
}

function formatPercent(value) {
    const numeric = Number(value || 0);
    const percent = numeric <= 1 ? numeric * 100 : numeric;
    return `${percent.toFixed(1)}%`;
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
            homeValue: `${getStatValue(homeStats, ['fgm', 'fieldGoalsMade'])}-${getStatValue(homeStats, ['fga', 'fieldGoalsAttempted'])}`,
            awayValue: `${getStatValue(awayStats, ['fgm', 'fieldGoalsMade'])}-${getStatValue(awayStats, ['fga', 'fieldGoalsAttempted'])}`,
            homeCompare: Number(getStatValue(homeStats, ['fgm', 'fieldGoalsMade'])),
            awayCompare: Number(getStatValue(awayStats, ['fgm', 'fieldGoalsMade']))
        },
        {
            label: 'FG%',
            homeValue: formatPercent(getStatValue(homeStats, ['fg_pct', 'fieldGoalsPercentage'])),
            awayValue: formatPercent(getStatValue(awayStats, ['fg_pct', 'fieldGoalsPercentage'])),
            homeCompare: Number(getStatValue(homeStats, ['fg_pct', 'fieldGoalsPercentage'])),
            awayCompare: Number(getStatValue(awayStats, ['fg_pct', 'fieldGoalsPercentage']))
        },
        {
            label: '3-Pointers',
            homeValue: `${getStatValue(homeStats, ['fg3m', 'threePointersMade'])}-${getStatValue(homeStats, ['fg3a', 'threePointersAttempted'])}`,
            awayValue: `${getStatValue(awayStats, ['fg3m', 'threePointersMade'])}-${getStatValue(awayStats, ['fg3a', 'threePointersAttempted'])}`,
            homeCompare: Number(getStatValue(homeStats, ['fg3m', 'threePointersMade'])),
            awayCompare: Number(getStatValue(awayStats, ['fg3m', 'threePointersMade']))
        },
        {
            label: '3P%',
            homeValue: formatPercent(getStatValue(homeStats, ['fg3_pct', 'threePointersPercentage'])),
            awayValue: formatPercent(getStatValue(awayStats, ['fg3_pct', 'threePointersPercentage'])),
            homeCompare: Number(getStatValue(homeStats, ['fg3_pct', 'threePointersPercentage'])),
            awayCompare: Number(getStatValue(awayStats, ['fg3_pct', 'threePointersPercentage']))
        },
        {
            label: 'Free Throws',
            homeValue: `${getStatValue(homeStats, ['ftm', 'freeThrowsMade'])}-${getStatValue(homeStats, ['fta', 'freeThrowsAttempted'])}`,
            awayValue: `${getStatValue(awayStats, ['ftm', 'freeThrowsMade'])}-${getStatValue(awayStats, ['fta', 'freeThrowsAttempted'])}`,
            homeCompare: Number(getStatValue(homeStats, ['ftm', 'freeThrowsMade'])),
            awayCompare: Number(getStatValue(awayStats, ['ftm', 'freeThrowsMade']))
        },
        {
            label: 'FT%',
            homeValue: formatPercent(getStatValue(homeStats, ['ft_pct', 'freeThrowsPercentage'])),
            awayValue: formatPercent(getStatValue(awayStats, ['ft_pct', 'freeThrowsPercentage'])),
            homeCompare: Number(getStatValue(homeStats, ['ft_pct', 'freeThrowsPercentage'])),
            awayCompare: Number(getStatValue(awayStats, ['ft_pct', 'freeThrowsPercentage']))
        },
        {
            label: 'Rebounds',
            homeValue: getStatValue(homeStats, ['rebounds', 'reb', 'reboundsTotal']),
            awayValue: getStatValue(awayStats, ['rebounds', 'reb', 'reboundsTotal']),
            homeCompare: Number(getStatValue(homeStats, ['rebounds', 'reb', 'reboundsTotal'])),
            awayCompare: Number(getStatValue(awayStats, ['rebounds', 'reb', 'reboundsTotal']))
        },
        {
            label: 'Assists',
            homeValue: getStatValue(homeStats, ['assists', 'ast']),
            awayValue: getStatValue(awayStats, ['assists', 'ast']),
            homeCompare: Number(getStatValue(homeStats, ['assists', 'ast'])),
            awayCompare: Number(getStatValue(awayStats, ['assists', 'ast']))
        },
        {
            label: 'Steals',
            homeValue: getStatValue(homeStats, ['steals', 'stl']),
            awayValue: getStatValue(awayStats, ['steals', 'stl']),
            homeCompare: Number(getStatValue(homeStats, ['steals', 'stl'])),
            awayCompare: Number(getStatValue(awayStats, ['steals', 'stl']))
        },
        {
            label: 'Blocks',
            homeValue: getStatValue(homeStats, ['blocks', 'blk']),
            awayValue: getStatValue(awayStats, ['blocks', 'blk']),
            homeCompare: Number(getStatValue(homeStats, ['blocks', 'blk'])),
            awayCompare: Number(getStatValue(awayStats, ['blocks', 'blk']))
        },
        {
            label: 'Turnovers',
            homeValue: getStatValue(homeStats, ['turnovers', 'turnoversTotal']),
            awayValue: getStatValue(awayStats, ['turnovers', 'turnoversTotal']),
            homeCompare: -Number(getStatValue(homeStats, ['turnovers', 'turnoversTotal'])),
            awayCompare: -Number(getStatValue(awayStats, ['turnovers', 'turnoversTotal']))
        }
    ];

    container.innerHTML = stats.map((stat) => {
        const homeHighlight = stat.homeCompare > stat.awayCompare ? 'highlight' : '';
        const awayHighlight = stat.awayCompare > stat.homeCompare ? 'highlight' : '';

        return `
            <div class="stat-row">
                <div class="stat-value ${awayHighlight}">${stat.awayValue}</div>
                <div class="stat-label">${stat.label}</div>
                <div class="stat-value ${homeHighlight}">${stat.homeValue}</div>
            </div>
        `;
    }).join('');
}

function parseMinutesToSeconds(value) {
    if (!value) return 0;
    if (typeof value === 'number') return value;

    if (typeof value === 'string' && value.startsWith('PT')) {
        const match = value.match(/PT(?:(\d+)M)?([\d.]+)S/);
        if (match) {
            const mins = Number(match[1] || 0);
            const secs = Math.floor(Number(match[2] || 0));
            return mins * 60 + secs;
        }
    }

    if (typeof value === 'string' && value.includes(':')) {
        const [mins, secs] = value.split(':').map(Number);
        return (Number(mins) || 0) * 60 + (Number(secs) || 0);
    }

    return Number(value) || 0;
}

function formatMinutes(value) {
    const totalSeconds = parseMinutesToSeconds(value);
    const mins = Math.floor(totalSeconds / 60);
    const secs = Math.round(totalSeconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function getPlayerStats(player) {
    if (player.statistics) return player.statistics;

    return {
        seconds: parseMinutesToSeconds(player.minutes),
        minutesCalculated: parseMinutesToSeconds(player.minutes),
        points: player.points || 0,
        fieldGoalsMade: player.fgm || 0,
        fieldGoalsAttempted: player.fga || 0,
        threePointersMade: player.fg3m || 0,
        threePointersAttempted: player.fg3a || 0,
        freeThrowsMade: player.ftm || 0,
        freeThrowsAttempted: player.fta || 0,
        reboundsTotal: player.rebounds || 0,
        assists: player.assists || 0,
        steals: player.steals || 0,
        blocks: player.blocks || 0,
        turnovers: player.turnovers || 0,
        foulsPersonal: player.fouls || 0,
        plusMinusPoints: player.plusMinus || 0
    };
}

function displayBoxScore(teamType, team) {
    const tableId = `${teamType}-boxscore`;
    const titleId = `${teamType}-team-boxscore-title`;
    const table = document.getElementById(tableId);
    const title = document.getElementById(titleId);

    title.textContent = `${team.teamCity} ${team.teamName} Box Score`;

    if (!team.players || team.players.length === 0) {
        table.innerHTML = '<tr><td colspan="14">Box score not available</td></tr>';
        return;
    }

    const sortedPlayers = [...team.players].sort((a, b) => {
        const minutesA = getPlayerStats(a).minutesCalculated || getPlayerStats(a).seconds || 0;
        const minutesB = getPlayerStats(b).minutesCalculated || getPlayerStats(b).seconds || 0;
        return minutesB - minutesA;
    });

    const starters = sortedPlayers.filter((player) => player.starter);
    const bench = sortedPlayers.filter((player) => !player.starter);

    let html = `
        <thead>
            <tr>
                <th>Player</th>
                <th>MIN</th>
                <th>PTS</th>
                <th>FG</th>
                <th>3PT</th>
                <th>FT</th>
                <th>REB</th>
                <th>AST</th>
                <th>STL</th>
                <th>BLK</th>
                <th>TO</th>
                <th>PF</th>
                <th>+/-</th>
            </tr>
        </thead>
        <tbody>
    `;

    starters.forEach((player) => {
        const stats = getPlayerStats(player);
        const plusMinus = stats.plusMinusPoints || 0;
        const plusMinusClass = plusMinus > 0 ? 'positive' : plusMinus < 0 ? 'negative' : '';

        html += `
            <tr>
                <td>
                    <div class="player-name">
                        <span class="jersey-num">${player.jerseyNum || '--'}</span>
                        <span>${player.name}</span>
                        <span class="position">${player.position || ''}</span>
                    </div>
                </td>
                <td>${formatMinutes(stats.seconds)}</td>
                <td>${stats.points || 0}</td>
                <td>${stats.fieldGoalsMade || 0}-${stats.fieldGoalsAttempted || 0}</td>
                <td>${stats.threePointersMade || 0}-${stats.threePointersAttempted || 0}</td>
                <td>${stats.freeThrowsMade || 0}-${stats.freeThrowsAttempted || 0}</td>
                <td>${stats.reboundsTotal || 0}</td>
                <td>${stats.assists || 0}</td>
                <td>${stats.steals || 0}</td>
                <td>${stats.blocks || 0}</td>
                <td>${stats.turnovers || 0}</td>
                <td>${stats.foulsPersonal || 0}</td>
                <td class="${plusMinusClass}">${plusMinus > 0 ? '+' : ''}${plusMinus}</td>
            </tr>
        `;
    });

    if (bench.length > 0) {
        html += '<tr class="bench-header"><td colspan="13">Bench</td></tr>';

        bench.forEach((player) => {
            const stats = getPlayerStats(player);
            const plusMinus = stats.plusMinusPoints || 0;
            const plusMinusClass = plusMinus > 0 ? 'positive' : plusMinus < 0 ? 'negative' : '';

            html += `
                <tr>
                    <td>
                        <div class="player-name">
                            <span class="jersey-num">${player.jerseyNum || '--'}</span>
                            <span>${player.name}</span>
                            <span class="position">${player.position || ''}</span>
                        </div>
                    </td>
                    <td>${formatMinutes(stats.seconds)}</td>
                    <td>${stats.points || 0}</td>
                    <td>${stats.fieldGoalsMade || 0}-${stats.fieldGoalsAttempted || 0}</td>
                    <td>${stats.threePointersMade || 0}-${stats.threePointersAttempted || 0}</td>
                    <td>${stats.freeThrowsMade || 0}-${stats.freeThrowsAttempted || 0}</td>
                    <td>${stats.reboundsTotal || 0}</td>
                    <td>${stats.assists || 0}</td>
                    <td>${stats.steals || 0}</td>
                    <td>${stats.blocks || 0}</td>
                    <td>${stats.turnovers || 0}</td>
                    <td>${stats.foulsPersonal || 0}</td>
                    <td class="${plusMinusClass}">${plusMinus > 0 ? '+' : ''}${plusMinus}</td>
                </tr>
            `;
        });
    }

    html += '</tbody>';
    table.innerHTML = html;
}

function displayNameForComment(comment) {
    const savedUserId = Number(String(readSavedUserId()).trim());
    const displayName = String(readSavedDisplayName()).trim();

    if (savedUserId && Number(comment.user_id) === savedUserId && displayName) {
        return displayName;
    }

    return comment.user_name || `User ${comment.user_id}`;
}

function renderComments(comments) {
    if (!Array.isArray(comments) || comments.length === 0) {
        commentsList.innerHTML = '<div class="game-comment-empty">No comments yet. Be the first one to talk about the game.</div>';
        return;
    }

    commentsList.innerHTML = comments.map((comment) => `
        <div class="game-comment-shot-card${comment.parent_comment_id ? ' reply' : ''}">
            <div class="game-comment-shot-author">${escapeHtml(displayNameForComment(comment))}</div>
            <div class="game-comment-shot-date">${escapeHtml(formatCommentDate(comment.created_at))}</div>
            <div class="game-comment-shot-text">${escapeHtml(comment.comment_text)}</div>
        </div>
    `).join('');
}

async function loadGameComments() {
    try {
        const comments = await fetchJson(`${API_BASE}/api/games/${gameId}/comments`);
        renderComments(comments);
    } catch (error) {
        console.error('Error loading game comments:', error);
        commentsList.innerHTML = `<div class="game-comment-empty">Could not load comments: ${escapeHtml(error.message)}</div>`;
    }
}

async function postGameComment() {
    const userId = ensureUserId();
    const commentText = String(commentTextInput.value || '').trim();

    if (!userId || !commentText) {
        alert('Enter a comment first.');
        return;
    }

    persistDisplayName();

    try {
        postCommentBtn.disabled = true;
        await fetchJson(`${API_BASE}/api/games/${gameId}/comments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                comment_text: commentText
            })
        });
        commentTextInput.value = '';
        await loadGameComments();
    } catch (error) {
        alert(error.message || 'Could not post comment.');
    } finally {
        postCommentBtn.disabled = false;
    }
}

function startCommentRefreshLoop() {
    if (commentsRefreshTimer) clearInterval(commentsRefreshTimer);
    commentsRefreshTimer = setInterval(loadGameComments, 30000);
}

commentDisplayNameInput.value = readSavedDisplayName();
commentDisplayNameInput.addEventListener('change', persistDisplayName);
postCommentBtn.addEventListener('click', postGameComment);

fetchGameDetail();
startCommentRefreshLoop();
setInterval(fetchGameDetail, 50000);

applyBackLink();
