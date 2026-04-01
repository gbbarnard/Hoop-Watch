const HOOPWATCH_AUTH_USER_KEY = 'hoopwatch_current_user';
const HOOPWATCH_AUTH_TOKEN_KEY = 'hoopwatch_auth_token';
const HOOPWATCH_USER_ID_KEY = 'hoopwatch_user_id';
const HOOPWATCH_TOAST_MESSAGE_KEY = 'hoopwatch_toast_message';
const HOOPWATCH_TOAST_TYPE_KEY = 'hoopwatch_toast_type';

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
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

function queueToast(message, type = 'success') {
  sessionStorage.setItem(HOOPWATCH_TOAST_MESSAGE_KEY, message);
  sessionStorage.setItem(HOOPWATCH_TOAST_TYPE_KEY, type);
}

function flushQueuedToast() {
  const message = sessionStorage.getItem(HOOPWATCH_TOAST_MESSAGE_KEY);
  if (!message) return;
  const type = sessionStorage.getItem(HOOPWATCH_TOAST_TYPE_KEY) || 'success';
  sessionStorage.removeItem(HOOPWATCH_TOAST_MESSAGE_KEY);
  sessionStorage.removeItem(HOOPWATCH_TOAST_TYPE_KEY);
  showToast(message, type);
}

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
  const message = 'You have successfully logged out.';

  if (window.location.pathname.endsWith('/account.html') || window.location.pathname.endsWith('/admin.html')) {
    queueToast(message, 'success');
    window.location.href = 'login.html';
    return;
  }

  showToast(message, 'success');
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

function initAuthUI() {
  renderNavAuth();
  flushQueuedToast();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAuthUI);
} else {
  initAuthUI();
}

window.HoopWatchAuth = {
  readStoredAuthUser,
  readStoredAuthToken,
  isAdminUser,
  storeAuthSession,
  clearAuthSession,
  logoutAuthUser,
  renderNavAuth,
  queueToast,
  HOOPWATCH_AUTH_USER_KEY,
  HOOPWATCH_AUTH_TOKEN_KEY,
  HOOPWATCH_USER_ID_KEY,
};
