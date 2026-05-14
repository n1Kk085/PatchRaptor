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
    setInterval(fetchData, 10000); // 10s poll
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

    // 2. Render/Update Server List
    const container = document.getElementById('server-list-container');
    if (!container) return;

    if (!data.servers || data.servers.length === 0) {
        container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">No servers available.</div>';
        return;
    }

    // Remove "No servers" message if it exists
    if (container.children.length === 1 && container.children[0].style.textAlign === 'center') {
        container.innerHTML = '';
    }

    const currentServerIds = data.servers.map(s => `server-card-${s.name}`);

    // Update or Create cards
    data.servers.forEach(server => {
        const cardId = `server-card-${server.name}`;
        let card = document.getElementById(cardId);
        
        if (!card) {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = createServerCard(server, cardId);
            container.appendChild(tempDiv.firstElementChild);
        } else {
            updateServerCardContent(card, server);
        }
    });

    // Remove stale cards
    Array.from(container.children).forEach(child => {
        if (child.id && child.id.startsWith('server-card-') && !currentServerIds.includes(child.id)) {
            container.removeChild(child);
        }
    });
}

function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el && el.textContent !== String(value)) {
        el.textContent = value;
    }
}

function updateServerCardContent(card, server) {
    // Only update if values actually changed to minimize DOM thrashing
    const pCountEl = card.querySelector('.val-pcount');
    if (pCountEl) pCountEl.textContent = server.playerCount;

    const statusEl = card.querySelector('.server-status');
    const statusTextEl = card.querySelector('.val-statustext');
    const statusText = server.status === 'online' ? 'ONLINE' : 'OFFLINE';
    if (statusEl) {
        statusEl.className = `server-status ${server.status === 'online' ? 'status-online' : 'status-offline'}`;
    }
    if (statusTextEl) {
        statusTextEl.textContent = statusText;
    }

    const cpuEl = card.querySelector('.val-cpu');
    if (cpuEl) cpuEl.textContent = `${(server.cpu || 0).toFixed(1)}%`;

    const ramEl = card.querySelector('.val-ram');
    if (ramEl) ramEl.textContent = `${(server.ram || 0).toFixed(1)} GB`;

    const uptimeEl = card.querySelector('.val-uptime');
    if (uptimeEl) uptimeEl.textContent = `${(server.uptime7day || 0).toFixed(1)}%`;

    const avgEl = card.querySelector('.val-avg');
    if (avgEl) avgEl.textContent = (server.playerAvg7day || 0).toFixed(1);
}

function createServerCard(server, cardId) {
    const statusClass = server.status === 'online' ? 'status-online' : 'status-offline';
    const statusText = server.status === 'online' ? 'ONLINE' : 'OFFLINE';
    const mapImage = server.mapimage || '/static/maps/default.jpg';
    const safeName = escapeHtml(server.displayName || server.name);

    return `
    <div class="server-card" id="${cardId}">
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
                        <span class="val-pcount">${server.playerCount}</span>
                    </div>
                </div>
                <div class="server-bottom">
                    <div class="server-status ${statusClass}">
                        <span class="dot"></span> <span class="val-statustext">${statusText}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="server-stats-grid">
            <div class="stat-item">
                <span class="stat-label">CPU</span>
                <span class="stat-val text-orange val-cpu">${(server.cpu || 0).toFixed(1)}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">RAM</span>
                <span class="stat-val text-blue val-ram">${(server.ram || 0).toFixed(1)} GB</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Uptime</span>
                <span class="stat-val text-purple val-uptime">${(server.uptime7day || 0).toFixed(1)}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">7d Avg</span>
                <span class="stat-val text-yellow val-avg">${(server.playerAvg7day || 0).toFixed(1)}</span>
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

