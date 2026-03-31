const API_BASE = 'http://localhost:8000';

const authMessage = document.getElementById('auth-message');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');

function showAuthMessage(message, type = 'error') {
  authMessage.hidden = false;
  authMessage.textContent = message;
  authMessage.className = `auth-message ${type}`;
}

function clearAuthMessage() {
  authMessage.hidden = true;
  authMessage.textContent = '';
  authMessage.className = 'auth-message';
}

function setAuthTab(tabName) {
  document.querySelectorAll('.auth-tab-btn').forEach((button) => {
    button.classList.toggle('active', button.dataset.authTab === tabName);
  });

  const loginActive = tabName === 'login';
  loginForm.classList.toggle('active', loginActive);
  loginForm.hidden = !loginActive;
  registerForm.classList.toggle('active', !loginActive);
  registerForm.hidden = loginActive;
  clearAuthMessage();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
  return data;
}

document.addEventListener('click', (event) => {
  const tabButton = event.target.closest('.auth-tab-btn[data-auth-tab]');
  if (tabButton) setAuthTab(tabButton.dataset.authTab);
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearAuthMessage();

  const identifier = document.getElementById('login-identifier').value.trim();
  const password = document.getElementById('login-password').value;

  try {
    const result = await fetchJson(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password })
    });

    window.HoopWatchAuth.storeAuthSession(result.user, result.token);
    window.location.href = 'account.html';
  } catch (error) {
    showAuthMessage(error.message || 'Could not log in.');
  }
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearAuthMessage();

  const displayName = document.getElementById('register-display-name').value.trim();
  const username = document.getElementById('register-username').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;
  const confirmPassword = document.getElementById('register-confirm-password').value;

  if (password !== confirmPassword) {
    showAuthMessage('Passwords do not match.');
    return;
  }

  try {
    const result = await fetchJson(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_name: displayName,
        username,
        email,
        password
      })
    });

    window.HoopWatchAuth.storeAuthSession(result.user, result.token);
    window.location.href = 'account.html';
  } catch (error) {
    showAuthMessage(error.message || 'Could not create account.');
  }
});

const existingUser = window.HoopWatchAuth.readStoredAuthUser();
if (existingUser) {
  window.location.href = 'account.html';
}
