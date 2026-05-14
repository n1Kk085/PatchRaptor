/**
 * PatchRaptor Dashboard Logic
 * Handles real-time updates for the Web Panel.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

function initDashboard() {
    fetchUserInfo();
    fetchData();
    setInterval(fetchData, 30000); // 30s poll
}

async function fetchUserInfo() {
    try {
        const response = await fetch('/api/me');
        if (response.ok) {
            const data = await response.json();
            const username = data.username;
            // Capitalize first letter
            const formattedName = username.charAt(0).toUpperCase() + username.slice(1);
            document.getElementById('dashboard-title').textContent = `${formattedName} Dashboard`;
        }
    } catch (error) {
        console.error('Error fetching user info:', error);
    }
}

async function fetchData() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
    }
}

function updateDashboard(data) {
    // 1. Update Top Stats
    updateElement('total-players', data.totalPlayers || 0);
    updateElement('online-servers', data.onlineCount || 0);
    updateElement('avg-uptime', (data.total7dayUptimeAvg || 0).toFixed(1) + '%');
    updateElement('avg-players', (data.total7dayPlayerAvg || 0).toFixed(1));
    updateElement('last-update', data.lastUpdate ? new Date(data.lastUpdate).toLocaleTimeString() : 'Never');
    updateElement('last-update-header', data.lastUpdate ? new Date(data.lastUpdate).toLocaleTimeString() : 'Never');

    // 2. Render Server List
    const container = document.getElementById('server-list-container');
    if (!container) return;

    if (!data.servers || data.servers.length === 0) {
        container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">No servers available.</div>';
        return;
    }

    container.innerHTML = data.servers.map(server => createServerCard(server)).join('');
}

function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function createServerCard(server) {
    const statusClass = server.status === 'online' ? 'status-online' : 'status-offline';
    const statusText = server.status === 'online' ? 'ONLINE' : 'OFFLINE';
    const mapImage = server.mapimage || '/static/maps/default.jpg';

    // Using inline styles/classes compatible with the new style.css
    // Sanitize server name to prevent XSS
    const safeName = escapeHtml(server.displayName || server.name);

    return `
    <div class="server-card">
        <div class="server-header" style="background-image: url('${mapImage}');">
            <div class="server-overlay">
                <div class="server-top">
                    <h3 class="server-name">${safeName}</h3>
                    <div class="server-pcount">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;">
                            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                            <circle cx="9" cy="7" r="4"></circle>
                            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                        </svg>
                        ${server.playerCount}
                    </div>
                </div>
                <div class="server-bottom">
                    <div class="server-status ${statusClass}">
                        <span class="dot"></span> ${statusText}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="server-stats-grid">
            <div class="stat-item">
                <span class="stat-label">CPU</span>
                <span class="stat-val text-orange">${(server.cpu || 0).toFixed(1)}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">RAM</span>
                <span class="stat-val text-blue">${(server.ram || 0).toFixed(1)} GB</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Uptime</span>
                <span class="stat-val text-green">${(server.uptime7day || 0).toFixed(1)}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">7d Avg</span>
                <span class="stat-val text-purple">${(server.server7dayAvg || 0).toFixed(1)}</span>
            </div>
        </div>
    </div>
    `;
}

function escapeHtml(text) {
    if (!text) return text;
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
