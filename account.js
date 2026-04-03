const ACCOUNT_API_BASE = 'http://localhost:8000';

const lockedView = document.getElementById('account-locked');
const contentView = document.getElementById('account-content');
const messageBox = document.getElementById('account-message');
const accountForm = document.getElementById('account-form');
const logoutButton = document.getElementById('account-logout-btn');
const avatarBox = document.getElementById('account-avatar');
const adminPanel = document.getElementById('account-admin-panel');
const ACCOUNT_USER_ID_KEY = window.HoopWatchAuth?.HOOPWATCH_USER_ID_KEY || 'hoopwatch_user_id';

const welcomeTitle = document.getElementById('account-welcome-title');
const welcomeSubtitle = document.getElementById('account-welcome-subtitle');

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

function readStoredAccountIdentity() {
  const storedUser = window.HoopWatchAuth.readStoredAuthUser();
  const token = window.HoopWatchAuth.readStoredAuthToken();
  const rawUserId = localStorage.getItem(ACCOUNT_USER_ID_KEY) || storedUser?.user_id || '';
  const parsedUserId = Number(rawUserId);

  return {
    user: storedUser,
    token,
    userId: Number.isFinite(parsedUserId) && parsedUserId > 0 ? parsedUserId : null,
  };
}

function updateWelcomeBanner(user) {
  if (!welcomeTitle || !welcomeSubtitle) return;

  const username = (user?.username || user?.display_name || user?.email || '').toString().trim();
  if (username) {
    welcomeTitle.textContent = `Welcome ${username}`;
    welcomeSubtitle.textContent = 'You are signed in to your account.';
  } else {
    welcomeTitle.textContent = 'Welcome';
    welcomeSubtitle.textContent = 'You are signed in to your account.';
  }
}

function setAccountGateState(allowed) {
  lockedView.hidden = !allowed;
  contentView.hidden = !allowed;
}

function setAvatarText(user) {
  const source = user?.display_name || user?.username || user?.email || 'HW';
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

function populateAccountForm(user = {}) {
  document.getElementById('account-display-name').value = user.display_name || '';
  document.getElementById('account-username').value = user.username || '';
  document.getElementById('account-email').value = user.email || '';
  document.getElementById('account-bio').value = user.bio || '';
  setAvatarText(user);
  syncAdminPanel(user);
  updateWelcomeBanner(user);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
  return data;
}

async function loadAccountProfile() {
  const { user, token, userId } = readStoredAccountIdentity();

  if (!user && (!token || !userId)) {
    setAccountGateState(false);
    syncAdminPanel(null);
    updateWelcomeBanner(null);
    return;
  }

  setAccountGateState(true);

  if (user) {
    populateAccountForm(user);
    clearAccountMessage();
  }

  if (!token || !userId) {
    showAccountMessage('Showing your saved account info. Log in again if you want to refresh or edit this page.', 'error');
    return;
  }

  try {
    const profile = await fetchJson(`${ACCOUNT_API_BASE}/api/users/${userId}/profile`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    populateAccountForm(profile);
    window.HoopWatchAuth.storeAuthSession(profile, token);
    clearAccountMessage();
  } catch (error) {
    const message = error.message || 'Could not load account profile.';

    if (user) {
      populateAccountForm(user);
      showAccountMessage('Showing your saved account info right now. Log in again if this page still will not refresh.', 'error');
      return;
    }

    setAccountGateState(false);
    syncAdminPanel(null);
    updateWelcomeBanner(null);
    showAccountMessage(message, 'error');
  }
}

accountForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearAccountMessage();

  const { token, userId, user } = readStoredAccountIdentity();
  if (!token || !userId) {
    setAccountGateState(true);
    if (user) populateAccountForm(user);
    showAccountMessage('Please log in again before saving account changes.', 'error');
    return;
  }

  try {
    const updated = await fetchJson(`${ACCOUNT_API_BASE}/api/users/${userId}/profile`, {
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
    populateAccountForm(updated);
    document.getElementById('account-current-password').value = '';
    document.getElementById('account-new-password').value = '';
    showAccountMessage('Account updated successfully.', 'success');
  } catch (error) {
    const message = error.message || 'Could not update account.';
    if (user) {
      populateAccountForm(user);
    }
    showAccountMessage(message, 'error');
  }
});

logoutButton?.addEventListener('click', () => {
  window.HoopWatchAuth.logoutAuthUser();
});

loadAccountProfile();
