const ADMIN_API_BASE = 'http://localhost:8000';

const adminLockedView = document.getElementById('admin-locked');
const adminContentView = document.getElementById('admin-content');
const adminMessageBox = document.getElementById('admin-message');
const adminContentDateInput = document.getElementById('admin-content-date');
const adminQotdDateInput = document.getElementById('admin-qotd-date');
const adminFactTextInput = document.getElementById('admin-fact-text');
const adminFeaturedGameSelect = document.getElementById('admin-featured-game-select');
const adminTeamsSelect = document.getElementById('admin-teams-to-watch');
const adminQotdTextInput = document.getElementById('admin-qotd-text');
const adminQotdOpenInput = document.getElementById('admin-qotd-open');
const adminCommentsBody = document.getElementById('admin-comments-body');

let adminProfile = null;
let allTeams = [];
let allSeasonGames = [];

function getAdminHeaders() {
  const token = window.HoopWatchAuth.readStoredAuthToken();
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`
  };
}

function showAdminMessage(message, type = 'error') {
  adminMessageBox.hidden = false;
  adminMessageBox.textContent = message;
  adminMessageBox.className = `auth-message ${type}`;
}

function clearAdminMessage() {
  adminMessageBox.hidden = true;
  adminMessageBox.textContent = '';
  adminMessageBox.className = 'auth-message';
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDateTime(value) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function getTodayString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data?.error || data?.message || `Request failed (${response.status})`);
  }

  return data;
}

function setAdminGateState(allowed) {
  adminLockedView.hidden = allowed;
  adminContentView.hidden = !allowed;
}

async function verifyAdminAccess() {
  const storedUser = window.HoopWatchAuth.readStoredAuthUser();
  const token = window.HoopWatchAuth.readStoredAuthToken();

  if (!storedUser || !token) {
    setAdminGateState(false);
    return false;
  }

  try {
    const profile = await fetchJson(`${ADMIN_API_BASE}/api/users/${storedUser.user_id}/profile`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    adminProfile = profile;
    window.HoopWatchAuth.storeAuthSession(profile, token);

    if (!window.HoopWatchAuth.isAdminUser(profile)) {
      setAdminGateState(false);
      return false;
    }

    setAdminGateState(true);
    return true;
  } catch (error) {
    setAdminGateState(false);
    showAdminMessage(error.message || 'Could not verify admin access.');
    return false;
  }
}

function renderDashboardStats(summary) {
  const stats = summary?.stats || {};
  document.getElementById('admin-total-users').textContent = stats.total_users ?? 0;
  document.getElementById('admin-tracked-today').textContent = stats.tracked_today ?? 0;
  document.getElementById('admin-last-sync').textContent = stats.last_sync ? formatDateTime(stats.last_sync) : '--';
  document.getElementById('admin-open-reports').textContent = stats.open_reports ?? 0;
}

function filterGamesByDate(dateString) {
  return allSeasonGames.filter((game) => game?.game_date === dateString);
}

function renderFeaturedGameOptions(dateString, selectedGameId = '') {
  const filteredGames = filterGamesByDate(dateString);
  const optionMarkup = ['<option value="">No featured game selected</option>'];

  filteredGames.forEach((game) => {
    const internalId = game.game_id || '';
    const awayName = game?.away_team?.abbreviation || game?.away_team?.full_name || 'Away';
    const homeName = game?.home_team?.abbreviation || game?.home_team?.full_name || 'Home';
    const label = `${awayName} vs ${homeName} • ${game.game_time || 'TBD'} • ${game.status || 'Scheduled'}`;
    optionMarkup.push(`<option value="${escapeHtml(internalId)}">${escapeHtml(label)}</option>`);
  });

  adminFeaturedGameSelect.innerHTML = optionMarkup.join('');
  if (selectedGameId) {
    adminFeaturedGameSelect.value = String(selectedGameId);
  }
}

function renderTeamOptions(selectedTeamIds = []) {
  const selectedSet = new Set(selectedTeamIds.map((value) => String(value)));
  adminTeamsSelect.innerHTML = allTeams
    .map((team) => {
      const teamId = String(team.team_id || team.id || '');
      const label = `${team.name} (${team.abbreviation})`;
      return `<option value="${escapeHtml(teamId)}" ${selectedSet.has(teamId) ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    })
    .join('');
}

function getSelectedTeamIds() {
  return Array.from(adminTeamsSelect.selectedOptions || []).map((option) => Number(option.value));
}

async function loadDashboardSummary() {
  const summary = await fetchJson(`${ADMIN_API_BASE}/api/admin/dashboard`, {
    headers: getAdminHeaders()
  });
  renderDashboardStats(summary);
}

async function loadTeams() {
  allTeams = await fetchJson(`${ADMIN_API_BASE}/api/teams`);
  renderTeamOptions([]);
}

async function loadSeasonGames() {
  allSeasonGames = await fetchJson(`${ADMIN_API_BASE}/api/games/season`);
}

async function loadDailyContent(dateString) {
  const data = await fetchJson(`${ADMIN_API_BASE}/api/admin/daily-content/${encodeURIComponent(dateString)}`, {
    headers: getAdminHeaders()
  });

  adminFactTextInput.value = data.fact_text || '';
  renderFeaturedGameOptions(dateString, data.featured_nba_game_id || data.featured_game_id || '');
}

async function loadTeamsToWatch(dateString) {
  const data = await fetchJson(`${ADMIN_API_BASE}/api/admin/teams-to-watch/${encodeURIComponent(dateString)}`, {
    headers: getAdminHeaders()
  });
  const selectedTeamIds = (data.teams || []).map((team) => team.team_id);
  renderTeamOptions(selectedTeamIds);
}

async function loadQotd(dateString) {
  const data = await fetchJson(`${ADMIN_API_BASE}/api/admin/qotd/${encodeURIComponent(dateString)}`, {
    headers: getAdminHeaders()
  });
  adminQotdTextInput.value = data.question_text || '';
  adminQotdOpenInput.checked = data.is_open !== false;
}

function renderCommentsTable(comments = []) {
  if (!comments.length) {
    adminCommentsBody.innerHTML = `
      <tr>
        <td colspan="5" class="admin-empty-cell">No comments found.</td>
      </tr>
    `;
    return;
  }

  adminCommentsBody.innerHTML = comments
    .map((comment) => `
      <tr>
        <td>${escapeHtml(comment.source_type || '--')}</td>
        <td>${escapeHtml(comment.user_name || '--')}</td>
        <td>${escapeHtml(comment.comment_text || '')}</td>
        <td>${escapeHtml(formatDateTime(comment.created_at))}</td>
        <td>
          <button
            type="button"
            class="admin-remove-btn"
            data-comment-id="${escapeHtml(comment.comment_id)}"
            data-source-type="${escapeHtml(comment.source_type)}"
          >Remove</button>
        </td>
      </tr>
    `)
    .join('');
}

async function loadComments() {
  const data = await fetchJson(`${ADMIN_API_BASE}/api/admin/comments?limit=20`, {
    headers: getAdminHeaders()
  });
  renderCommentsTable(data.comments || []);
}

async function loadDateScopedContent(dateString) {
  renderFeaturedGameOptions(dateString, '');
  await Promise.all([
    loadDailyContent(dateString),
    loadTeamsToWatch(dateString),
    loadQotd(dateString)
  ]);
}

async function initializeAdminPage() {
  clearAdminMessage();

  const allowed = await verifyAdminAccess();
  if (!allowed) return;

  const today = getTodayString();
  adminContentDateInput.value = today;
  adminQotdDateInput.value = today;

  try {
    await Promise.all([
      loadDashboardSummary(),
      loadTeams(),
      loadSeasonGames(),
      loadComments()
    ]);

    await loadDateScopedContent(today);
  } catch (error) {
    showAdminMessage(error.message || 'Could not load admin dashboard data.');
  }
}

async function saveDailyContent() {
  const dateString = adminContentDateInput.value;
  if (!dateString) {
    showAdminMessage('Choose a content date first.');
    return;
  }

  await fetchJson(`${ADMIN_API_BASE}/api/admin/daily-content/${encodeURIComponent(dateString)}`, {
    method: 'PUT',
    headers: getAdminHeaders(),
    body: JSON.stringify({
      fact_text: adminFactTextInput.value.trim(),
      featured_game_id: adminFeaturedGameSelect.value || null
    })
  });

  showAdminMessage('Home page content saved.', 'success');
  await loadDashboardSummary();
}

async function saveTeamsToWatch() {
  const dateString = adminContentDateInput.value;
  if (!dateString) {
    showAdminMessage('Choose a content date first.');
    return;
  }

  await fetchJson(`${ADMIN_API_BASE}/api/admin/teams-to-watch/${encodeURIComponent(dateString)}`, {
    method: 'PUT',
    headers: getAdminHeaders(),
    body: JSON.stringify({ team_ids: getSelectedTeamIds() })
  });

  showAdminMessage('Teams to watch saved.', 'success');
  await loadDashboardSummary();
}

async function saveQotd() {
  const dateString = adminQotdDateInput.value;
  if (!dateString) {
    showAdminMessage('Choose a QOTD date first.');
    return;
  }

  await fetchJson(`${ADMIN_API_BASE}/api/admin/qotd/${encodeURIComponent(dateString)}`, {
    method: 'PUT',
    headers: getAdminHeaders(),
    body: JSON.stringify({
      question_text: adminQotdTextInput.value.trim(),
      is_open: adminQotdOpenInput.checked
    })
  });

  showAdminMessage('Question of the day saved.', 'success');
  await loadDashboardSummary();
}

async function runAdminSync(syncKey, button) {
  const routeMap = {
    teams: 'sync-teams',
    standings: 'sync-standings',
    players: 'sync-players',
    'player-stats': 'sync-player-stats',
    'completed-game-details': 'sync-completed-game-details'
  };

  const route = routeMap[syncKey];
  if (!route) return;

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = 'Working...';

  try {
    const data = await fetchJson(`${ADMIN_API_BASE}/api/admin/${route}`, {
      headers: getAdminHeaders()
    });

    const detailBits = [];
    if (Number.isFinite(data?.players_upserted)) {
      detailBits.push(`players updated: ${data.players_upserted}`);
    }
    if (Number.isFinite(data?.stats_rows_upserted)) {
      detailBits.push(`stat rows updated: ${data.stats_rows_upserted}`);
    }
    if (Number.isFinite(data?.players_still_missing_stats)) {
      detailBits.push(`still missing stats: ${data.players_still_missing_stats}`);
    }
    if (Number.isFinite(data?.players_seen)) {
      detailBits.push(`players seen: ${data.players_seen}`);
    }
    if (Number.isFinite(data?.players_bio_updated)) {
      detailBits.push(`bios updated: ${data.players_bio_updated}`);
    }
    if (Number.isFinite(data?.fields_filled)) {
      detailBits.push(`fields filled: ${data.fields_filled}`);
    }
    if (Number.isFinite(data?.players_missing_birth_date)) {
      detailBits.push(`missing birth dates: ${data.players_missing_birth_date}`);
    }
    if (Number.isFinite(data?.players_missing_height)) {
      detailBits.push(`missing heights: ${data.players_missing_height}`);
    }
    if (Number.isFinite(data?.players_missing_weight)) {
      detailBits.push(`missing weights: ${data.players_missing_weight}`);
    }

    const successMessage = data?.message
      ? `${data.message}${detailBits.length ? ` (${detailBits.join(' • ')})` : ''}`
      : `${originalText} finished.`;

    showAdminMessage(successMessage, 'success');
    await loadDashboardSummary();
  } catch (error) {
    showAdminMessage(error.message || `Could not run ${originalText}.`);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

document.getElementById('admin-reload-content-btn')?.addEventListener('click', async () => {
  clearAdminMessage();
  const dateString = adminContentDateInput.value || getTodayString();
  adminQotdDateInput.value = dateString;

  try {
    await loadDateScopedContent(dateString);
    showAdminMessage('Admin content reloaded for that date.', 'success');
  } catch (error) {
    showAdminMessage(error.message || 'Could not reload admin content.');
  }
});

document.getElementById('admin-save-daily-content-btn')?.addEventListener('click', async () => {
  clearAdminMessage();
  try {
    await saveDailyContent();
  } catch (error) {
    showAdminMessage(error.message || 'Could not save home page content.');
  }
});

document.getElementById('admin-clear-daily-content-btn')?.addEventListener('click', () => {
  adminFactTextInput.value = '';
  adminFeaturedGameSelect.value = '';
  showAdminMessage('Home page fields cleared on the page. Save to apply.', 'success');
});

document.getElementById('admin-save-teams-btn')?.addEventListener('click', async () => {
  clearAdminMessage();
  try {
    await saveTeamsToWatch();
  } catch (error) {
    showAdminMessage(error.message || 'Could not save teams to watch.');
  }
});

document.getElementById('admin-clear-teams-btn')?.addEventListener('click', () => {
  Array.from(adminTeamsSelect.options).forEach((option) => {
    option.selected = false;
  });
  showAdminMessage('Teams to watch cleared on the page. Save to apply.', 'success');
});

document.getElementById('admin-save-qotd-btn')?.addEventListener('click', async () => {
  clearAdminMessage();
  try {
    await saveQotd();
  } catch (error) {
    showAdminMessage(error.message || 'Could not save the question of the day.');
  }
});

document.getElementById('admin-clear-qotd-btn')?.addEventListener('click', () => {
  adminQotdTextInput.value = '';
  adminQotdOpenInput.checked = true;
  showAdminMessage('QOTD fields cleared on the page. Save to apply.', 'success');
});

document.getElementById('admin-refresh-comments-btn')?.addEventListener('click', async () => {
  clearAdminMessage();
  try {
    await loadComments();
    showAdminMessage('Comments refreshed.', 'success');
  } catch (error) {
    showAdminMessage(error.message || 'Could not refresh comments.');
  }
});

document.addEventListener('click', async (event) => {
  const syncButton = event.target.closest('[data-admin-sync]');
  if (syncButton) {
    clearAdminMessage();
    await runAdminSync(syncButton.dataset.adminSync, syncButton);
    return;
  }

  const removeButton = event.target.closest('.admin-remove-btn');
  if (removeButton) {
    clearAdminMessage();
    try {
      await fetchJson(
        `${ADMIN_API_BASE}/api/admin/comments/${encodeURIComponent(removeButton.dataset.sourceType)}/${encodeURIComponent(removeButton.dataset.commentId)}`,
        {
          method: 'DELETE',
          headers: getAdminHeaders()
        }
      );
      await loadComments();
      showAdminMessage('Comment removed.', 'success');
    } catch (error) {
      showAdminMessage(error.message || 'Could not remove comment.');
    }
  }
});

adminContentDateInput?.addEventListener('change', () => {
  renderFeaturedGameOptions(adminContentDateInput.value || getTodayString(), adminFeaturedGameSelect.value || '');
});

adminQotdDateInput?.addEventListener('change', async () => {
  clearAdminMessage();
  try {
    await loadQotd(adminQotdDateInput.value || getTodayString());
  } catch (error) {
    showAdminMessage(error.message || 'Could not load that QOTD date.');
  }
});

initializeAdminPage();
