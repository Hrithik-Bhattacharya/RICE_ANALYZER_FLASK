/* ============================================
   RICE GRAIN ANALYZER - REALTIME CONTROLLER
   Health-First Architecture
   ============================================ */

let isRunning = false;
let pollInterval = null;
let uptimeInterval = null;
let startTime = null;
let healthPollInterval = null;
let isPiHealthy = false;

// DOM Elements
const btnStart = document.getElementById('btnStart');
const btnStop = document.getElementById('btnStop');
const btnShutdown = document.getElementById('btnShutdown');
const statusBadge = document.getElementById('systemStatus');
const healthBadge = document.getElementById('healthStatus');
const healthDot = document.getElementById('healthDot');
const healthText = document.getElementById('healthText');
const healthDetails = document.getElementById('healthDetails');
const healthLatency = document.getElementById('healthLatency');
const healthCamera = document.getElementById('healthCamera');
const videoFeed = document.getElementById('videoFeed');
const videoPlaceholder = document.getElementById('videoPlaceholder');
const fpsValue = document.getElementById('fpsValue');
const fpsDot = document.getElementById('fpsDot');
const uptimeEl = document.getElementById('uptime');

// Counter elements
const counterElements = {
    total: document.getElementById('countTotal'),
    chalky: document.getElementById('countChalky'),
    white: document.getElementById('countWhite'),
    brown: document.getElementById('countBrown'),
    black: document.getElementById('countBlack'),
    broken: document.getElementById('countBroken'),
    other: document.getElementById('countOther')
};

// ============================================
// API CALLS
// ============================================

async function apiCall(endpoint, method = 'POST') {
    try {
        const response = await fetch(endpoint, { method: method });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        showNotification('Error: ' + error.message, 'error');
        return null;
    }
}

// ============================================
// HEALTH CHECK MONITORING (Every 5 seconds)
// ============================================

async function pollHealthStatus() {
    try {
        const response = await fetch('/api/health');
        if (!response.ok) {
            updateHealthUI(false, 'Server Error', null);
            return;
        }

        const data = await response.json();
        const health = data.health || {};
        const isHealthy = data.is_healthy || false;

        isPiHealthy = isHealthy;

        // Update UI based on health
        if (health.online && health.camera_started && health.camera_configured) {
            updateHealthUI(true, 'Pi Ready', health);
        } else if (health.online) {
            updateHealthUI(false, 'Pi Online - Camera Not Ready', health);
        } else {
            updateHealthUI(false, 'Pi Offline', health);
        }

        // Enable/disable start button based on health
        if (!isRunning) {
            btnStart.disabled = !isHealthy;
        }

    } catch (error) {
        console.error('Health poll error:', error);
        isPiHealthy = false;
        updateHealthUI(false, 'No Response', null);
        if (!isRunning) btnStart.disabled = true;
    }
}

function updateHealthUI(isHealthy, text, healthData) {
    healthText.textContent = text;

    // Remove all status classes
    healthBadge.classList.remove('health-online', 'health-offline', 'health-checking');
    healthDot.classList.remove('online', 'offline');

    if (isHealthy) {
        healthBadge.classList.add('health-online');
        healthDot.classList.add('online');

        let tooltip = 'Raspberry Pi is online\nCamera is configured and started';
        if (healthData && healthData.latency_ms) {
            tooltip += `\nLatency: ${healthData.latency_ms}ms`;
            healthLatency.textContent = `⚡ ${healthData.latency_ms}ms`;
        }
        healthBadge.setAttribute('data-tooltip', tooltip);
        healthCamera.textContent = '📷 Camera Ready';
        healthDetails.style.display = 'flex';

    } else {
        healthBadge.classList.add('health-offline');
        healthDot.classList.add('offline');

        let tooltip = 'Raspberry Pi is not reachable\nor camera is not ready';
        if (healthData && healthData.error) {
            tooltip += `\nError: ${healthData.error}`;
        }
        healthBadge.setAttribute('data-tooltip', tooltip);
        healthLatency.textContent = '';
        healthCamera.textContent = healthData && healthData.camera_started ? '📷 Camera Started' : '📷 Camera Not Ready';
        healthDetails.style.display = 'flex';
    }
}

// ============================================
// SYSTEM CONTROLS (Health-First)
// ============================================

function startSystem() {
    if (isRunning) return;

    // CRITICAL: Check health before starting
    if (!isPiHealthy) {
        showNotification('Cannot start: Pi is not healthy. Check connection.', 'error');
        return;
    }

    apiCall('/api/start').then(data => {
        if (data && data.success) {
            isRunning = true;
            startTime = Date.now();

            btnStart.disabled = true;
            btnStop.disabled = false;

            statusBadge.textContent = 'Analyzing...';
            statusBadge.className = 'status-badge status-active';

            fpsDot.classList.add('active');

            // Switch to live video feed
            videoFeed.innerHTML = `<img src="/video_feed" alt="Live Camera Feed" onerror="handleVideoError()">`;

            // Start polling for counters
            pollInterval = setInterval(pollCounters, 100);
            uptimeInterval = setInterval(updateUptime, 1000);

            showNotification('System started - Rice flow active', 'success');
        } else if (data && !data.success) {
            showNotification(data.message || 'Failed to start', 'error');
        }
    });
}

function stopSystem() {
    if (!isRunning) return;

    apiCall('/api/stop').then(data => {
        if (data && data.success) {
            isRunning = false;

            clearInterval(pollInterval);
            clearInterval(uptimeInterval);

            btnStart.disabled = !isPiHealthy;  // Re-enable only if Pi is healthy
            btnStop.disabled = true;

            statusBadge.textContent = 'System Idle';
            statusBadge.className = 'status-badge status-idle';

            fpsDot.classList.remove('active');
            fpsValue.textContent = '0 FPS';

            // Reset video to placeholder
            videoFeed.innerHTML = `
                <div class="video-placeholder" id="videoPlaceholder">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                        <circle cx="8.5" cy="8.5" r="1.5"></circle>
                        <polyline points="21 15 16 10 5 21"></polyline>
                    </svg>
                    <p>Camera Feed Standby</p>
                    <p style="font-size: 0.8rem; margin-top: 5px; opacity: 0.6;">
                        ${isPiHealthy ? 'Press Start to begin analysis' : 'Waiting for Pi to come online...'}
                    </p>
                </div>
            `;

            showNotification('System stopped', 'info');
        }
    });
}

function shutdownSystem() {
    if (isRunning) {
        stopSystem();
    }

    if (!confirm('Are you sure you want to shutdown the Raspberry Pi?')) {
        return;
    }

    apiCall('/api/shutdown').then(data => {
        if (data && data.success) {
            statusBadge.textContent = 'Shutting Down...';
            statusBadge.className = 'status-badge status-shutdown';

            videoFeed.innerHTML = `
                <div style="text-align: center; color: #ee5a5a;">
                    <div style="font-size: 3rem; margin-bottom: 10px;">⏻️</div>
                    <p style="font-weight: 700; font-size: 1.1rem;">System Shutting Down</p>
                    <p style="font-size: 0.85rem; opacity: 0.7; margin-top: 5px;">Raspberry Pi will power off shortly...</p>
                </div>
            `;

            btnStart.disabled = true;
            btnStop.disabled = true;
            btnShutdown.disabled = true;

            showNotification('Shutdown command sent to Raspberry Pi', 'warning');
        }
    });
}

// ============================================
// REALTIME COUNTER POLLING (from shared file)
// ============================================

async function pollCounters() {
    try {
        const response = await fetch('/api/counters');
        if (!response.ok) return;

        const data = await response.json();

        updateCounterDisplay('total', data.counters.total);
        updateCounterDisplay('chalky', data.counters.chalky);
        updateCounterDisplay('white', data.counters.white);
        updateCounterDisplay('brown', data.counters.brown);
        updateCounterDisplay('black', data.counters.black);
        updateCounterDisplay('broken', data.counters.broken);
        updateCounterDisplay('other', data.counters.other);

        fpsValue.textContent = data.fps + ' FPS';
        uptimeEl.textContent = data.uptime;

    } catch (error) {
        console.error('Counter polling error:', error);
    }
}

function updateCounterDisplay(type, newValue) {
    const el = counterElements[type];
    if (!el) return;

    const currentValue = parseInt(el.textContent) || 0;

    if (newValue !== currentValue) {
        el.textContent = newValue;
        el.classList.add('updated');
        setTimeout(() => el.classList.remove('updated'), 400);
    }
}

// ============================================
// UPTIME CALCULATION
// ============================================

function updateUptime() {
    if (!startTime) return;

    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
    const seconds = (elapsed % 60).toString().padStart(2, '0');

    uptimeEl.textContent = `${hours}:${minutes}:${seconds}`;
}

// ============================================
// VIDEO ERROR HANDLER
// ============================================

function handleVideoError() {
    console.error('Video feed error');
    videoFeed.innerHTML = `
        <div style="text-align: center; color: #ee5a5a;">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">⚠️</div>
            <p style="font-weight: 700;">Camera Feed Error</p>
            <p style="font-size: 0.85rem; opacity: 0.7; margin-top: 5px;">Connection to Pi lost. Health check will attempt reconnect.</p>
        </div>
    `;
}

// ============================================
// NOTIFICATION SYSTEM
// ============================================

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification-toast');
    if (existing) existing.remove();

    const colors = {
        success: '#6bcb77',
        error: '#ff6b6b',
        warning: '#ffd93d',
        info: '#8ecae6'
    };

    const toast = document.createElement('div');
    toast.className = 'notification-toast';
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 15px 25px;
        border-radius: 20px;
        font-weight: 700;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease;
        font-family: 'Nunito', sans-serif;
    `;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add keyframe animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100px); opacity: 0; }
    }
`;
document.head.appendChild(style);

// ============================================
// KEYBOARD SHORTCUTS
// ============================================

document.addEventListener('keydown', (e) => {
    if (e.key === ' ' && e.target === document.body) {
        e.preventDefault();
        if (isRunning) {
            stopSystem();
        } else if (isPiHealthy) {
            startSystem();
        }
    }
    if (e.key === 'Escape') {
        stopSystem();
    }
});

// ============================================
// INITIALIZATION - HEALTH FIRST
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🌾 Rice Grain Analyzer initialized');
    console.log('Health-first mode: Pi must be online before starting');

    // Disable start button until health check passes
    btnStart.disabled = true;

    // Show checking state
    healthBadge.classList.add('health-checking');

    // Start health monitoring immediately (every 5 seconds)
    pollHealthStatus();
    healthPollInterval = setInterval(pollHealthStatus, 5000);

    console.log('Keyboard shortcuts: SPACE = Start/Stop (if healthy), ESC = Stop');
});
