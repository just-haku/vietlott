/**
 * SOUL · Experiments Timeline Module
 * Renders the timeline of runs and visualizes score trends using Canvas.
 */

import { api, subscribe } from './app.js';

let container = null;
let rawExperiments = [];
let currentFilter = 'all';

export async function init(targetElement) {
    container = targetElement;
    await loadData();
    render();
    
    // Subscribe to SSE updates for live updates
    subscribe('experiment-added', (newExp) => {
        rawExperiments.unshift(newExp); // add to beginning
        render();
    });
}

async function loadData() {
    try {
        rawExperiments = await api.get('/api/experiments');
    } catch (err) {
        console.error("Failed to load experiments", err);
    }
}

function render() {
    if (!container) return;
    
    const filtered = rawExperiments.filter(exp => {
        if (currentFilter === 'improved') return exp.status === 'improved';
        return true;
    });
    
    const timelineItemsHtml = filtered.map(exp => {
        const dateStr = new Date(exp.timestamp).toLocaleTimeString();
        const statusClass = exp.status === 'improved' ? 'improved' : '';
        const icon = exp.status === 'improved' ? '🎉' : '⚙️';
        const badgeText = exp.status === 'improved' ? 'KEPT (IMPROVED)' : 'DISCARDED';
        
        return `
            <div class="timeline-item ${statusClass}">
                <span class="timeline-icon">${icon}</span>
                <div class="timeline-details">
                    <div class="timeline-meta">
                        <span class="timeline-id">Exp #${exp.id}</span>
                        <span>${dateStr}</span>
                    </div>
                    <div class="timeline-desc">
                        <strong>${badgeText}</strong>: ${exp.description || 'Running research step.'}
                    </div>
                    <div class="timeline-score" style="margin-top: 6px; font-size: 0.8rem; color: var(--text-muted);">
                        Train Score: <span style="color:#fff">${Number(exp.train_score).toFixed(4)}</span> | 
                        Test Score: <span class="text-accent">${Number(exp.test_score).toFixed(4)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = `
        <div class="chart-container" style="margin-bottom: 20px;">
            <div class="chart-title">Entropy Over Experiments (Lower is Better)</div>
            <div class="chart-wrapper">
                <canvas id="experiments-canvas" class="chart-canvas"></canvas>
            </div>
        </div>
        
        <div class="timeline-list">
            ${timelineItemsHtml || '<div class="info-empty">No experiments recorded yet. Click Start to begin.</div>'}
        </div>
    `;
    
    // Setup filter button listeners
    const cardEl = container.closest('.card');
    if (cardEl) {
        cardEl.querySelectorAll('.filter-btn').forEach(btn => {
            btn.onclick = (e) => {
                cardEl.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                render();
            };
        });
    }
    
    // Draw trend chart
    drawChart();
}

function drawChart() {
    const canvas = document.getElementById('experiments-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    
    // Set internal resolution matching CSS size
    canvas.width = width;
    canvas.height = height;
    
    if (rawExperiments.length < 2) {
        ctx.fillStyle = '#8e8e93';
        ctx.font = '12px Inter';
        ctx.textAlign = 'center';
        ctx.fillText('Waiting for data to draw score timeline...', width / 2, height / 2);
        return;
    }
    
    // We reverse history so older runs are on the left
    const history = [...rawExperiments].reverse();
    
    // Margins
    const margin = { top: 20, right: 20, bottom: 20, left: 40 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    
    // Find min and max scores for scaling
    let allScores = history.flatMap(e => [e.train_score, e.test_score]);
    let minScore = Math.min(...allScores);
    let maxScore = Math.max(...allScores);
    
    // Guard against identical values
    if (minScore === maxScore) {
        minScore -= 0.1;
        maxScore += 0.1;
    } else {
        const padding = (maxScore - minScore) * 0.1;
        minScore = Math.max(0, minScore - padding);
        maxScore += padding;
    }
    
    // Draw Grid Lines
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = margin.top + (plotHeight * (i / 4));
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(width - margin.right, y);
        ctx.stroke();
        
        // Y Labels
        const val = maxScore - ((maxScore - minScore) * (i / 4));
        ctx.fillStyle = '#8e8e93';
        ctx.font = '9px monospace';
        ctx.textAlign = 'right';
        ctx.fillText(val.toFixed(2), margin.left - 8, y + 3);
    }
    
    // Map data points
    const getX = (index) => margin.left + (plotWidth * (index / (history.length - 1)));
    const getY = (score) => margin.top + plotHeight - (plotHeight * ((score - minScore) / (maxScore - minScore)));
    
    // Draw Train Score line
    ctx.beginPath();
    ctx.strokeStyle = '#00d4ff';
    ctx.lineWidth = 2;
    history.forEach((exp, i) => {
        const x = getX(i);
        const y = getY(exp.train_score);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    // Draw Test Score line
    ctx.beginPath();
    ctx.strokeStyle = '#7b2fff';
    ctx.lineWidth = 2;
    history.forEach((exp, i) => {
        const x = getX(i);
        const y = getY(exp.test_score);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    // Highlight kept/improved runs as dots
    history.forEach((exp, i) => {
        if (exp.status === 'improved') {
            const x = getX(i);
            const y = getY(exp.test_score);
            ctx.fillStyle = '#00e676';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    });
}
