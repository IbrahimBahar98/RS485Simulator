// JS Simulator — Login Script

// Default credentials
const DEFAULT_CREDENTIALS = {
  username: 'admin',
  password: 'admin'
};

// DOM Elements
const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');

// Login handler
function handleLogin(event) {
  event.preventDefault();

  const username = usernameInput.value.trim();
  const password = passwordInput.value.trim();

  if (username === DEFAULT_CREDENTIALS.username && password === DEFAULT_CREDENTIALS.password) {
    // ✅ Success: simulate transition to main app UI
    console.log('Login successful — loading main interface...');
    
    // In a real Electron app, this would load the main window content
    // For now, we'll simulate rendering the 3-panel layout
    showMainLayout();
    
  } else {
    // ❌ Failure
    alert('Invalid credentials. Try username: "admin", password: "admin"');
    passwordInput.select();
  }
}

// Simulate loading main 3-panel layout
function showMainLayout() {
  // Hide login container
  document.querySelector('.login-container').style.display = 'none';

  // Create main app shell
  const appShell = document.createElement('div');
  appShell.className = 'app-shell';
  appShell.innerHTML = `
    <div class="sidebar">
      <nav>
        <ul>
          <li><a href="#dashboard" class="active">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M3 9L12 2L21 9V21C21 21.5304 20.7893 22.0391 20.4142 22.4142C20.0391 22.7893 19.5304 23 19 23H5C4.46957 23 3.96086 22.7893 3.58579 22.4142C3.21071 22.0391 3 21.5304 3 21V9Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 23V12C9 11.4696 9.21071 10.9609 9.58579 10.5858C9.96086 10.2107 10.4696 10 11 10H13C13.5304 10 14.0391 10.2107 14.4142 10.5858C14.7893 10.9609 15 11.4696 15 12V23" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <span>Dashboard</span>
          </a></li>
          <li><a href="#users">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="8.5" cy="7" r="4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M20 8.5c0 2.5-2.5 4.5-5 4.5s-5-2-5-4.5c0-2.5 2.5-4.5 5-4.5s5 2 5 4.5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <span>Users</span>
          </a></li>
          <li><a href="#settings">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12.22 2.41c.33-.1.71-.1.99.05l.1.06c.34.2.5.57.4.9l-.21.72c-.1.33-.47.5-.79.4l-.73-.21c-.33-.1-.5-.57-.4-.9l.21-.72c.1-.33.47-.5.79-.4l.73.21Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M14.12 7.17c.33-.1.71-.1.99.05l.1.06c.34.2.5.57.4.9l-.21.72c-.1.33-.47.5-.79.4l-.73-.21c-.33-.1-.5-.57-.4-.9l.21-.72c.1-.33.47-.5.79-.4l.73.21Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M5.2 11.2c.33-.1.71-.1.99.05l.1.06c.34.2.5.57.4.9l-.21.72c-.1.33-.47.5-.79.4l-.73-.21c-.33-.1-.5-.57-.4-.9l.21-.72c.1-.33.47-.5.79-.4l.73.21Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M17.2 11.2c.33-.1.71-.1.99.05l.1.06c.34.2.5.57.4.9l-.21.72c-.1.33-.47.5-.79.4l-.73-.21c-.33-.1-.5-.57-.4-.9l.21-.72c.1-.33.47-.5.79-.4l.73.21Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M20.2 15.2c.33-.1.71-.1.99.05l.1.06c.34.2.5.57.4.9l-.21.72c-.1.33-.47.5-.79.4l-.73-.21c-.33-.1-.5-.57-.4-.9l.21-.72c.1-.33.47-.5.79-.4l.73.21Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M2.2 15.2c.33-.1.71-.1.99.05l.1.06c.34.2.5.57.4.9l-.21.72c-.1.33-.47.5-.79.4l-.73-.21c-.33-.1-.5-.57-.4-.9l.21-.72c.1-.33.47-.5.79-.4l.73.21Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 22.5c-4.6957 0-8.5-3.8043-8.5-8.5s3.8043-8.5 8.5-8.5 8.5 3.8043 8.5 8.5-3.8043 8.5-8.5 8.5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <span>Settings</span>
          </a></li>
        </ul>
      </nav>
    </div>
    <div class="main-panel">
      <h2>Users</h2>
      <div class="user-list" id="userList">
        <!-- populated dynamically -->
      </div>
    </div>
    <div class="right-panel">
      <div class="toolbar">
        <div class="search-box">
          <input type="text" placeholder="Search..." />
        </div>
        <button class="icon-btn" title="Add User">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
        <button class="icon-btn" title="Notifications">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M18 8A6 6 0 0 1 2 8c0 7-3 9-3 9h18c0 0-3-2-3-9Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M13.73 21a2 2 0 0 1-3.46 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="icon-btn" title="Profile">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15.5 20.488c.5.2 1 .2 1.5 0A2.6 2.6 0 0 0 21 17.288c0-3.2-2.5-6.2-5.5-6.2s-5.5 3-5.5 6.2c0 3.2 3.5 6.2 4.5 6.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
      <div class="detail-area">
        <h3>User Details</h3>
        <p>Select a user to view details.</p>
      </div>
    </div>
  `;

  document.body.appendChild(appShell);

  // Populate mock users
  const userList = document.getElementById('userList');
  const mockUsers = [
    { id: 1, name: 'Alex Morgan', avatar: 'AM' },
    { id: 2, name: 'Taylor Reed', avatar: 'TR' },
    { id: 3, name: 'Jordan Kim', avatar: 'JK' },
    { id: 4, name: 'Casey Liu', avatar: 'CL' },
    { id: 5, name: 'Riley Smith', avatar: 'RS' },
    { id: 6, name: 'Morgan Lee', avatar: 'ML' }
  ];

  mockUsers.forEach(user => {
    const userEl = document.createElement('div');
    userEl.className = 'user-item';
    userEl.innerHTML = `
      <div class="avatar">${user.avatar}</div>
      <div class="user-name">${user.name}</div>
    `;
    userList.appendChild(userEl);
  });

  // Add sidebar nav interactivity
  document.querySelectorAll('.sidebar nav a').forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      document.querySelectorAll('.sidebar nav a').forEach(a => a.classList.remove('active'));
      this.classList.add('active');
    });
  });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }
});