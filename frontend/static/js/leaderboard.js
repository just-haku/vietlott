/**
 * SOUL · Leaderboard Module
 * Renders the top 5 formula sets (brains) sorted by test entropy.
 */

import { api, subscribe } from './app.js';

let container = null;

export async function init(targetElement) {
    container = targetElement;
    await render();
    
    // Subscribe to events that should trigger a reload
    subscribe('leaderboard-updated', () => render());
}

async function render() {
    container.innerHTML = `
        <div class="skeleton-loader">
            <div class="skeleton-line short"></div>
            <div class="skeleton-card"></div>
        </div>
    `;
    
    try {
        const brains = await api.get('/api/brains');
        if (!brains || brains.length === 0) {
            container.innerHTML = `
                <div class="info-empty">
                    ☕ No brains registered yet. Running research will populate this leaderboard with formulas achieving low entropy.
                </div>
            `;
            return;
        }
        
        const listHtml = brains.map(brain => {
            const dateStr = new Date(brain.created_at).toLocaleString();
            
            // Format formulas block
            const formulasCode = Object.entries(brain.formulas || {})
                .map(([feat, expr]) => `"${feat}": "${expr}"`)
                .join(',\n  ');
            
            return `
                <div class="leaderboard-card">
                    <div class="brain-header">
                        <div class="header-logo-group">
                            <span class="rank-badge">${brain.rank}</span>
                            <span class="brain-id">${brain.id}</span>
                        </div>
                        <span class="brain-score">${Number(brain.score).toFixed(4)}</span>
                    </div>
                    <div class="brain-desc">${brain.description || 'No description provided.'}</div>
                    
                    <button class="brain-formulas-toggle" data-target="formulas-${brain.id}">
                        <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 5.83L15.17 9l1.41-1.41L12 3 7.41 7.59 8.83 9 12 5.83zm0 12.34L8.83 15l-1.41 1.41L12 21l4.59-4.59-1.43-1.41-3.16 3.16z"/></svg>
                        View Formula Set
                    </button>
                    
                    <pre id="formulas-${brain.id}" class="brain-formulas"><code class="language-json">{\n  ${formulasCode}\n}</code></pre>
                    
                    <div class="timeline-meta" style="margin-top:8px;">
                        <span>Created: ${dateStr}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = `
            <div class="leaderboard-list">
                ${listHtml}
            </div>
        `;
        
        // Bind formula toggle events
        container.querySelectorAll('.brain-formulas-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.dataset.target;
                const pre = container.querySelector(`#${targetId}`);
                if (pre) {
                    pre.classList.toggle('visible');
                }
            });
        });
        
    } catch (err) {
        container.innerHTML = `<div class="error-msg">⚠️ Failed to load leaderboard.</div>`;
    }
}
