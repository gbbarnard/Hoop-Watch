const API_BASE = "http://localhost:8000";
const USER_ID_STORAGE_KEY = "hoopwatch_user_id";

const userChip = document.getElementById("myfeed-user-chip");
const changeUserBtn = document.getElementById("change-user-btn");

const repliesList = document.getElementById("comment-replies-list");
const favoritesList = document.getElementById("favorites-list");
const watchlistList = document.getElementById("watchlist-list");
const alertsList = document.getElementById("alerts-list");

function formatDate(dateString) {
  const date = new Date(dateString);

  return date.toLocaleDateString("en-US", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function readSavedUserId() {
    return localStorage.getItem(USER_ID_STORAGE_KEY) || "";
}

function promptForUserId() {
    const entered = window.prompt("Enter your demo user ID to load My Feed. Example: 2");
    const userId = Number(String(entered || "").trim());

    if (!userId || userId < 1) {
        alert("A valid user ID is required to open My Feed.");
        return null;
    }

    localStorage.setItem(USER_ID_STORAGE_KEY, String(userId));
    return userId;
}

function getActiveUserId() {
    const saved = Number(String(readSavedUserId()).trim());
    if (saved > 0) return saved;
    return promptForUserId();
}

async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data?.error || data?.message || `${res.status} ${res.statusText}`);
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

function safeText(value) {
    return (value ?? "").toString();
}

function escapeHtml(value) {
    return safeText(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function formatDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return safeText(value);
    return date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit"
    });
}

function formatGameDate(value) {
    if (!value) return "Date TBD";
    const date = new Date(`${value}T12:00:00`);
    if (Number.isNaN(date.getTime())) return safeText(value);
    return date.toLocaleDateString([], {
        month: "short",
        day: "numeric",
        year: "numeric"
    });
}

function formatGameDateTime(gameDate, startTime) {
    if (!gameDate) return "Date TBD";
    if (!startTime) return formatGameDate(gameDate);

    const dateTimeStr = `${gameDate}T${startTime}`;
    const date = new Date(dateTimeStr);
    if (Number.isNaN(date.getTime())) return formatGameDate(gameDate);

    return date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit"
    });
}

function formatLiveClock(value) {
    if (!value) return "";

    // NBA API / game cache may provide ISO 8601 duration style like PT1M17.00S
    const isoDurationMatch = String(value).match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$/i);
    if (isoDurationMatch) {
        const hours = Number(isoDurationMatch[1] || 0);
        const minutes = Number(isoDurationMatch[2] || 0);
        const seconds = Number(isoDurationMatch[3] || 0);
        let totalSeconds = Math.floor(hours * 3600 + minutes * 60 + seconds);
        const displayHours = Math.floor(totalSeconds / 3600);
        totalSeconds = totalSeconds % 3600;
        const displayMinutes = Math.floor(totalSeconds / 60);
        const displaySeconds = totalSeconds % 60;

        if (displayHours > 0) {
            return `${displayHours}:${String(displayMinutes).padStart(2, "0")}:${String(displaySeconds).padStart(2, "0")}`;
        }
        return `${displayMinutes}:${String(displaySeconds).padStart(2, "0")}`;
    }

    // If it's already a conventional clock string, just return it
    return String(value);
}

function nbaLogoUrl(teamId) {
    return teamId ? `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg` : "";
}

function buildTeamName(team) {
    const name = safeText(team.name);
    const city = safeText(team.city);
    if (!name) return city || "Team";
    if (city && name.toLowerCase().startsWith(city.toLowerCase())) return name;
    return city ? `${city} ${name}` : name;
}

function buildGameLink(game) {
    return `game-detail.html?id=${encodeURIComponent(game.nba_game_id || game.game_identifier || game.game_id || "")}`;
}

function renderEmptyState(message) {
    return `<div class="myfeed-empty">${escapeHtml(message)}</div>`;
}

function setCount(id, count) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(count || 0);
}

function renderFavorites(items) {
    setCount("favorites-count", items.length);

    if (!items.length) {
        favoritesList.innerHTML = renderEmptyState("No favorite teams yet.");
        return;
    }

    favoritesList.innerHTML = items.map((team) => {
        const displayName = buildTeamName({ name: team.name, city: team.city });
        const logoSrc = team.logo_url || nbaLogoUrl(team.nba_team_id);
        return `
      <div class="myfeed-team-item">
        <a class="myfeed-team-main" href="team-detail.html?id=${encodeURIComponent(team.team_id)}">
          <div class="myfeed-team-logo-wrap">
            ${logoSrc ? `<img class="myfeed-team-logo" src="${escapeHtml(logoSrc)}" alt="${escapeHtml(displayName)}" onerror="this.onerror=null;this.src='${escapeHtml(nbaLogoUrl(team.nba_team_id))}'">` : '<span class="myfeed-logo-fallback">🏀</span>'}
          </div>
          <div class="myfeed-team-copy">
            <div class="myfeed-item-title">${escapeHtml(displayName)}</div>
            <div class="myfeed-item-subtext">${escapeHtml(safeText(team.abbreviation))} • ${Number(team.wins || 0)}-${Number(team.losses || 0)}</div>
          </div>
        </a>
        <div class="myfeed-item-actions">
          <button class="myfeed-secondary-btn small" type="button" onclick="removeFavoriteTeam('${team.team_id}')">Remove</button>
        </div>
      </div>
    `;
    }).join("");
}

function gameDisplayName(prefix, row) {
    return buildTeamName({ name: row[`${prefix}_name`], city: row[`${prefix}_city`] });
}

function gameLogo(prefix, row) {
    return row[`${prefix}_logo_url`] || nbaLogoUrl(row[`${prefix}_nba_team_id`]);
}

function gameStatusLine(row) {
    const status = safeText(row.status);

    if (status === "live") {
        const periodText = row.period ? `Q${row.period}` : "Live";
        const clockText = row.clock ? ` • ${formatLiveClock(row.clock)}` : "";
        return `Live • ${periodText}${clockText}`;
    }

    if (status === "final") {
        return `Final • ${formatGameDateTime(row.game_date, row.start_time)}`;
    }

    return `Upcoming • ${formatGameDateTime(row.game_date, row.start_time)}`;
}

function gameScoreLine(row) {
    const awayScore = row.away_score === null || row.away_score === undefined ? "-" : row.away_score;
    const homeScore = row.home_score === null || row.home_score === undefined ? "-" : row.home_score;
    return `${gameDisplayName("away", row)} ${awayScore} • ${homeScore} ${gameDisplayName("home", row)}`;
}

function renderGameCollection(container, items, countId, emptyMessage, removeMode) {
    setCount(countId, items.length);

    if (!items.length) {
        container.innerHTML = renderEmptyState(emptyMessage);
        return;
    }

    container.innerHTML = items.map((row) => {
        const identifier = encodeURIComponent(row.nba_game_id || row.game_identifier || row.game_id || "");
        const awayName = gameDisplayName("away", row);
        const homeName = gameDisplayName("home", row);
        const awayLogo = gameLogo("away", row);
        const homeLogo = gameLogo("home", row);
        const removeLabel = removeMode === "watchlist" ? "Remove" : "Turn Off";

        return `
      <div class="myfeed-game-item">
        <a class="myfeed-game-main" href="${buildGameLink(row)}">
          <div class="myfeed-game-teams-row">
            <div class="myfeed-game-team-mini">
              ${awayLogo ? `<img class="myfeed-team-mini-logo" src="${escapeHtml(awayLogo)}" alt="${escapeHtml(awayName)}">` : '<span class="myfeed-logo-fallback">🏀</span>'}
              <span>${escapeHtml(awayName)}</span>
            </div>
            <span class="myfeed-versus">vs</span>
            <div class="myfeed-game-team-mini">
              ${homeLogo ? `<img class="myfeed-team-mini-logo" src="${escapeHtml(homeLogo)}" alt="${escapeHtml(homeName)}">` : '<span class="myfeed-logo-fallback">🏀</span>'}
              <span>${escapeHtml(homeName)}</span>
            </div>
          </div>
          <div class="myfeed-item-subtext">${escapeHtml(gameStatusLine(row))}</div>
          <div class="myfeed-scoreline">${escapeHtml(gameScoreLine(row))}</div>
        </a>
        <div class="myfeed-item-actions">
          <button class="myfeed-secondary-btn small" type="button" onclick="removeSavedGame('${removeMode}', '${identifier}')">${removeLabel}</button>
        </div>
      </div>
    `;
    }).join("");
}

function renderReplies(items) {
    setCount("replies-count", items.length);

    if (!items.length) {
        repliesList.innerHTML = renderEmptyState("No one has replied to your comments yet.");
        return;
    }

    repliesList.innerHTML = items.map((reply) => {
        const isGame = safeText(reply.source_type) === "game";
        const title = isGame
            ? `${gameDisplayName("away", reply)} vs ${gameDisplayName("home", reply)}`
            : `QOTD • ${formatDate(reply.question_date) || "Question"}`
        const href = isGame
            ? buildGameLink(reply)
            : `qotd.html?date=${encodeURIComponent(reply.question_date || "")}`;

        return `
      <a class="myfeed-reply-item" href="${href}">
        <div class="myfeed-reply-topline">
          <span class="myfeed-item-title">${escapeHtml(title)}</span>
          <span class="myfeed-reply-date">${escapeHtml(formatDateTime(reply.reply_created_at))}</span>
        </div>
        <div class="myfeed-item-subtext">${escapeHtml(reply.replier_name || "Someone")} replied to your comment</div>
        <div class="myfeed-quote-block">
          <strong>You:</strong> ${escapeHtml(reply.your_comment_text || "")}
        </div>
        <div class="myfeed-quote-block reply">
          <strong>Reply:</strong> ${escapeHtml(reply.reply_text || "")}
        </div>
      </a>
    `;
    }).join("");
}

async function removeSavedGame(mode, gameIdentifier) {
    const userId = getActiveUserId();
    if (!userId || !gameIdentifier) return;

    const endpoint = mode === "watchlist"
        ? `${API_BASE}/api/games/${gameIdentifier}/watchlist/${userId}`
        : `${API_BASE}/api/games/${gameIdentifier}/alerts/${userId}`;

    try {
        await fetchJson(endpoint, { method: "DELETE" });
        await loadMyFeed();

        if (mode === "watchlist") {
            showToast("Removed game from watchlist", "success");
        } else {
            showToast("Game alert turned off", "success");
        }
    } catch (error) {
        showToast(error.message || "Could not update saved game item.", "error");
    }
}

window.removeSavedGame = removeSavedGame;

async function removeFavoriteTeam(teamId) {
    const userId = getActiveUserId();
    if (!userId || !teamId) return;

    try {
        await fetchJson(`${API_BASE}/api/users/${userId}/favorites/${teamId}`, { method: "DELETE" });
        await loadMyFeed();
        showToast("Removed team from favorites", "success");
    } catch (error) {
        showToast(error.message || "Could not remove favorite team.", "error");
    }
}

window.removeFavoriteTeam = removeFavoriteTeam;

async function loadMyFeed() {
    const userId = getActiveUserId();
    if (!userId) {
        repliesList.innerHTML = renderEmptyState("Set a user ID to load My Feed.");
        favoritesList.innerHTML = renderEmptyState("Set a user ID to load My Feed.");
        watchlistList.innerHTML = renderEmptyState("Set a user ID to load My Feed.");
        alertsList.innerHTML = renderEmptyState("Set a user ID to load My Feed.");
        return;
    }

    userChip.textContent = `User ID: ${userId}`;
    repliesList.innerHTML = '<div class="loading">Loading feed...</div>';
    favoritesList.innerHTML = '<div class="loading">Loading favorites...</div>';
    watchlistList.innerHTML = '<div class="loading">Loading watchlist...</div>';
    alertsList.innerHTML = '<div class="loading">Loading alerts...</div>';

    try {
        const data = await fetchJson(`${API_BASE}/api/users/${userId}/myfeed`);
        renderReplies(Array.isArray(data.comment_replies) ? data.comment_replies : []);
        renderFavorites(Array.isArray(data.favorites) ? data.favorites : []);
        renderGameCollection(watchlistList, Array.isArray(data.watchlist) ? data.watchlist : [], "watchlist-count", "No watchlisted games yet.", "watchlist");
        renderGameCollection(alertsList, Array.isArray(data.alerts) ? data.alerts : [], "alerts-count", "No game alerts saved yet.", "alerts");
    } catch (error) {
        const message = escapeHtml(error.message || "Could not load My Feed.");
        repliesList.innerHTML = `<div class="myfeed-empty">${message}</div>`;
        favoritesList.innerHTML = `<div class="myfeed-empty">${message}</div>`;
        watchlistList.innerHTML = `<div class="myfeed-empty">${message}</div>`;
        alertsList.innerHTML = `<div class="myfeed-empty">${message}</div>`;
    }
}

changeUserBtn.addEventListener("click", () => {
    localStorage.removeItem(USER_ID_STORAGE_KEY);
    const nextUserId = promptForUserId();
    if (nextUserId) loadMyFeed();
});

loadMyFeed();
