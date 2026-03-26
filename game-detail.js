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

if (!gameId) {
    window.location.href = 'index.html';
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

    const entered = window.prompt('Enter your demo user ID to post comments. Example: 2');
    const userId = Number(String(entered || '').trim());

    if (!userId || userId < 1) {
        alert('A valid user ID is required to post comments.');
        return null;
    }

    localStorage.setItem(USER_ID_STORAGE_KEY, String(userId));
    return userId;
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
            homeValue: homeStats.reb || 0,
            awayValue: awayStats.reb || 0,
            homeCompare: homeStats.reb || 0,
            awayCompare: awayStats.reb || 0
        },
        {
            label: 'Assists',
            homeValue: homeStats.ast || 0,
            awayValue: awayStats.ast || 0,
            homeCompare: homeStats.ast || 0,
            awayCompare: awayStats.ast || 0
        },
        {
            label: 'Steals',
            homeValue: homeStats.stl || 0,
            awayValue: awayStats.stl || 0,
            homeCompare: homeStats.stl || 0,
            awayCompare: awayStats.stl || 0
        },
        {
            label: 'Blocks',
            homeValue: homeStats.blk || 0,
            awayValue: awayStats.blk || 0,
            homeCompare: homeStats.blk || 0,
            awayCompare: awayStats.blk || 0
        },
        {
            label: 'Turnovers',
            homeValue: homeStats.turnovers || 0,
            awayValue: awayStats.turnovers || 0,
            homeCompare: -(homeStats.turnovers || 0),
            awayCompare: -(awayStats.turnovers || 0)
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

function formatMinutes(seconds) {
    if (seconds === null || seconds === undefined) return '0:00';
    const totalSeconds = Number(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = Math.round(totalSeconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
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

    const starters = team.players.filter((player) => player.statistics?.minutesCalculated > 0).sort((a, b) => {
        const minutesA = a.statistics?.minutesCalculated || 0;
        const minutesB = b.statistics?.minutesCalculated || 0;
        return minutesB - minutesA;
    });

    const bench = team.players.filter((player) => !starters.includes(player));

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
        const stats = player.statistics || {};
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
            const stats = player.statistics || {};
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

