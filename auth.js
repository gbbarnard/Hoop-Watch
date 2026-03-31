const HOOPWATCH_AUTH_USER_KEY = 'hoopwatch_current_user';
const HOOPWATCH_AUTH_TOKEN_KEY = 'hoopwatch_auth_token';
const HOOPWATCH_USER_ID_KEY = 'hoopwatch_user_id';

function authEscapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function readStoredAuthUser() {
  try {
    const raw = localStorage.getItem(HOOPWATCH_AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    console.error('Could not read stored auth user:', error);
    return null;
  }
}

function readStoredAuthToken() {
  return localStorage.getItem(HOOPWATCH_AUTH_TOKEN_KEY) || '';
}

function isAdminUser(user = readStoredAuthUser()) {
  return String(user?.role || '').toLowerCase() === 'admin';
}

function storeAuthSession(user, token) {
  if (user) {
    localStorage.setItem(HOOPWATCH_AUTH_USER_KEY, JSON.stringify(user));
    if (user.user_id) localStorage.setItem(HOOPWATCH_USER_ID_KEY, String(user.user_id));
  }
  if (token) localStorage.setItem(HOOPWATCH_AUTH_TOKEN_KEY, token);
  renderNavAuth();
}

function clearAuthSession() {
  localStorage.removeItem(HOOPWATCH_AUTH_USER_KEY);
  localStorage.removeItem(HOOPWATCH_AUTH_TOKEN_KEY);
  localStorage.removeItem(HOOPWATCH_USER_ID_KEY);
  renderNavAuth();
}

async function logoutAuthUser() {
  const token = readStoredAuthToken();

  if (token) {
    try {
      await fetch('http://localhost:8000/api/auth/logout', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
    } catch (error) {
      console.error('Logout request failed:', error);
    }
  }

  clearAuthSession();

  if (window.location.pathname.endsWith('/account.html') || window.location.pathname.endsWith('/admin.html')) {
    window.location.href = 'login.html';
  }
}

function renderNavAuth() {
  const slots = document.querySelectorAll('.nav-auth-slot');
  if (!slots.length) return;

  const user = readStoredAuthUser();

  slots.forEach((slot) => {
    if (!user) {
      slot.innerHTML = `
        <a href="login.html" class="nav-login-btn">Log In</a>
      `;
      return;
    }

    const displayName = user.display_name || user.username || user.email || `User ${user.user_id}`;
    slot.innerHTML = `
      <a href="account.html" class="nav-account-btn">${authEscapeHtml(displayName)}</a>
      <button type="button" class="nav-logout-btn">Log Out</button>
    `;
  });
}

document.addEventListener('click', (event) => {
  const logoutButton = event.target.closest('.nav-logout-btn');
  if (logoutButton) {
    logoutAuthUser();
  }
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', renderNavAuth);
} else {
  renderNavAuth();
}

window.HoopWatchAuth = {
  readStoredAuthUser,
  readStoredAuthToken,
  isAdminUser,
  storeAuthSession,
  clearAuthSession,
  logoutAuthUser,
  renderNavAuth,
  HOOPWATCH_AUTH_USER_KEY,
  HOOPWATCH_AUTH_TOKEN_KEY,
  HOOPWATCH_USER_ID_KEY,
};
