/**
 * SOUL · Vietlott Deterministic Universe — Frontend Orchestrator
 * Implements lazy loading of panels, state management, SSE listeners,
 * and command center controls.
 */

// Global State
export const state = {
    running: false,
    uptime: 0,
    experimentCount: 0,
    bestTestScore: null,
    activeModules: {},
    config: {
        provider: 'google',
        model: 'gemma-4-27b-it',
        temperature: 0.7,
        train_split: 0.85
    }
};

// Event emitter/subscribers pattern
const subscribers = {};
export function subscribe(event, callback) {
    if (!subscribers[event]) subscribers[event] = [];
    subscribers[event].push(callback);
}
export function publish(event, data) {
    if (!subscribers[event]) return;
    subscribers[event].forEach(cb => cb(data));
}

// Utility: Toast Notifications
export function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// API Helpers
export const api = {
    async get(url) {
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`API GET error on ${url}:`, err);
            showToast(`Connection error: ${err.message}`, 'error');
            throw err;
        }
    },
    async post(url, body = {}) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`API POST error on ${url}:`, err);
            showToast(`Command failed: ${err.message}`, 'error');
            throw err;
        }
    }
};

// Module Registry mapping section IDs to script URLs
const MODULE_REGISTRY = {
    'leaderboard': '/static/js/leaderboard.js',
    'experiments': '/static/js/experiments.js',
    'ai-panel': '/static/js/ai-panel.js',
    'config': '/static/js/config.js',
    'data-explorer': '/static/js/data-explorer.js'
};

// Lazy Loading Orchestrator
async function loadModule(name, element) {
    if (state.activeModules[name]) return;
    
    // Show loading state inside the panel body if not already present
    const body = element.querySelector('.panel-body');
    
    try {
        const moduleUrl = MODULE_REGISTRY[name];
        if (!moduleUrl) throw new Error(`Module URL not registered for: ${name}`);
        
        // Import module dynamically
        const module = await import(moduleUrl);
        
        // Initialize the module
        if (module.init) {
            await module.init(body);
        }
        
        state.activeModules[name] = module;
        console.log(`✦ Lazy loaded module: ${name}`);
    } catch (err) {
        console.error(`Failed to load module ${name}:`, err);
        if (body) {
            body.innerHTML = `<div class="error-msg">⚠️ Failed to load module. <button class="btn btn-primary btn-sm" onclick="location.reload()">Retry</button></div>`;
        }
    }
}

// Format Uptime Helper
function formatDuration(seconds) {
    if (!seconds) return '0s';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    let result = '';
    if (hrs > 0) result += `${hrs}h `;
    if (mins > 0 || hrs > 0) result += `${mins}m `;
    result += `${secs}s`;
    return result;
}

// Update Status indicators
function updateStatusUI() {
    const dot = document.querySelector('.status-dot');
    const text = document.getElementById('engine-status-text');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    
    if (state.running) {
        dot.className = 'status-dot active animate-pulse';
        text.innerText = 'Engine Running';
        btnStart.disabled = true;
        btnStop.disabled = false;
    } else {
        dot.className = 'status-dot stopped';
        text.innerText = 'Engine Idle';
        btnStart.disabled = false;
        btnStop.disabled = true;
    }
    
    document.getElementById('stat-uptime').innerText = formatDuration(state.uptime);
    document.getElementById('stat-experiments').innerText = state.experimentCount;
    document.getElementById('stat-best-score').innerText = 
        state.bestTestScore !== null ? Number(state.bestTestScore).toFixed(4) : 'N/A';
}

// Global SSE connection for AI feeds and status updates
let sseConnection = null;
function initSSE() {
    if (sseConnection) return;
    
    console.log("✦ Establishing Server-Sent Events stream...");
    sseConnection = new EventSource('/api/ai-responses');
    
    sseConnection.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            publish('sse-event', data);
            
            // Handle global state updates from SSE stream
            if (data.type === 'status') {
                state.running = data.data.running;
                updateStatusUI();
            } else if (data.type === 'experiment_complete') {
                state.experimentCount++;
                publish('experiment-added', data.data);
                if (data.data.improved) {
                    showToast('🎉 Found a better formula set!', 'success');
                    publish('leaderboard-updated', null);
                }
                updateStatusUI();
            }
        } catch (err) {
            console.error("Failed to parse SSE event:", err);
        }
    };
    
    sseConnection.onerror = () => {
        console.warn("SSE connection interrupted. Reconnecting in 5s...");
        sseConnection.close();
        sseConnection = null;
        setTimeout(initSSE, 5000);
    };
}

// Poll state periodically for robustness
async function pollStatus() {
    try {
        const data = await api.get('/api/status');
        state.running = data.running;
        state.uptime = data.uptime;
        state.experimentCount = data.experiment_count;
        state.bestTestScore = data.best_test_score || null;
        updateStatusUI();
    } catch (err) {
        console.error("Status polling failed");
    }
}

// Setup core application controls
function setupControls() {
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    
    btnStart.addEventListener('click', async () => {
        const res = await api.post('/api/research/start');
        if (res.status === 'started' || res.status === 'already_running') {
            state.running = true;
            showToast('Auto-research loop started', 'info');
            updateStatusUI();
        }
    });
    
    btnStop.addEventListener('click', async () => {
        const res = await api.post('/api/research/stop');
        if (res.status === 'stopped') {
            state.running = false;
            showToast('Stopping research loop...', 'info');
            updateStatusUI();
        }
    });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    // 1. Setup controls
    setupControls();
    
    // 2. Initial status poll
    pollStatus();
    setInterval(pollStatus, 5000);
    
    // 3. Establish EventSource (SSE)
    initSSE();
    
    // 4. Setup intersection observer for lazy loading panels
    const lazyObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const name = entry.target.dataset.module;
                loadModule(name, entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { rootMargin: '100px' });
    
    document.querySelectorAll('.lazy-section').forEach(section => {
        lazyObserver.observe(section);
    });
    
    // Robust collapsible layout for configuration
    const configHeader = document.querySelector('.collapsible-header');
    if (configHeader) {
        configHeader.addEventListener('click', () => {
            configHeader.classList.toggle('collapsed');
        });
    }
});
