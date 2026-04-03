const ACCOUNT_API_BASE = 'http://localhost:8000';

const lockedView = document.getElementById('account-locked');
const contentView = document.getElementById('account-content');
const messageBox = document.getElementById('account-message');
const accountForm = document.getElementById('account-form');
const logoutButton = document.getElementById('account-logout-btn');
const avatarBox = document.getElementById('account-avatar');
const adminPanel = document.getElementById('account-admin-panel');

function getAuthHeaders() {
  const token = window.HoopWatchAuth.readStoredAuthToken();
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`
  };
}

function showAccountMessage(message, type = 'error') {
  messageBox.hidden = false;
  messageBox.textContent = message;
  messageBox.className = `auth-message ${type}`;
}

function clearAccountMessage() {
  messageBox.hidden = true;
  messageBox.textContent = '';
  messageBox.className = 'auth-message';
}

function setAvatarText(user) {
  const source = user.display_name || user.username || user.email || 'HW';
  const initials = source
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('');
  avatarBox.textContent = initials || 'HW';
}

function syncAdminPanel(user) {
  if (!adminPanel) return;

  adminPanel.style.display = 'none';

  if (user && window.HoopWatchAuth.isAdminUser(user)) {
    adminPanel.style.display = 'block';
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
  return data;
}

async function loadAccountProfile() {
  const user = window.HoopWatchAuth.readStoredAuthUser();
  const token = window.HoopWatchAuth.readStoredAuthToken();

  if (!user || !token) {
    lockedView.hidden = false;
    contentView.hidden = true;
    syncAdminPanel(null);
    return;
  }

  lockedView.hidden = true;
  contentView.hidden = false;

  try {
    const profile = await fetchJson(`${ACCOUNT_API_BASE}/api/users/${user.user_id}/profile`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    document.getElementById('account-display-name').value = profile.display_name || '';
    document.getElementById('account-username').value = profile.username || '';
    document.getElementById('account-email').value = profile.email || '';
    document.getElementById('account-bio').value = profile.bio || '';
    setAvatarText(profile);
    syncAdminPanel(profile);
    window.HoopWatchAuth.storeAuthSession(profile, token);
  } catch (error) {
    showAccountMessage(error.message || 'Could not load account profile.');
  }
}

accountForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearAccountMessage();

  const user = window.HoopWatchAuth.readStoredAuthUser();
  const token = window.HoopWatchAuth.readStoredAuthToken();
  if (!user || !token) {
    lockedView.hidden = false;
    contentView.hidden = true;
    syncAdminPanel(null);
    return;
  }

  try {
    const updated = await fetchJson(`${ACCOUNT_API_BASE}/api/users/${user.user_id}/profile`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        display_name: document.getElementById('account-display-name').value.trim(),
        username: document.getElementById('account-username').value.trim(),
        email: document.getElementById('account-email').value.trim(),
        bio: document.getElementById('account-bio').value.trim(),
        current_password: document.getElementById('account-current-password').value,
        new_password: document.getElementById('account-new-password').value,
      })
    });

    window.HoopWatchAuth.storeAuthSession(updated, token);
    setAvatarText(updated);
    syncAdminPanel(updated);
    document.getElementById('account-current-password').value = '';
    document.getElementById('account-new-password').value = '';
    showAccountMessage('Account updated successfully.', 'success');
  } catch (error) {
    showAccountMessage(error.message || 'Could not update account.');
  }
});

logoutButton?.addEventListener('click', () => {
  window.HoopWatchAuth.logoutAuthUser();
});

loadAccountProfile();
