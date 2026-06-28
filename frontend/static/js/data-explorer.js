/**
 * SOUL · Vietlott Feature Explorer Module
 * Visualizes deterministic feature properties and splits using Canvas drawings.
 */

import { api } from './app.js';

let container = null;
let rawFeatures = [];
let selectedFeature = 'A';

export async function init(targetElement) {
    container = targetElement;
    await loadData();
    render();
}

async function loadData() {
    try {
        rawFeatures = await api.get('/api/features');
    } catch (err) {
        console.error("Failed to load feature dataset", err);
    }
}

function render() {
    if (!container) return;
    
    if (!rawFeatures || rawFeatures.length === 0) {
        container.innerHTML = `
            <div class="info-empty">
                📊 Dataset empty. Run the data analyzer script first to extract and cache features.
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="explorer-charts">
            <!-- Line Chart Container -->
            <div class="chart-container">
                <div class="chart-title" id="explorer-chart-title">Time-series Trend (Draws over Time)</div>
                <div class="chart-wrapper">
                    <canvas id="explorer-line-canvas" class="chart-canvas"></canvas>
                </div>
            </div>
            
            <!-- Distribution/Histogram Container -->
            <div class="chart-container">
                <div class="chart-title">Frequency Distribution</div>
                <div class="chart-wrapper">
                    <canvas id="explorer-dist-canvas" class="chart-canvas"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Summary Stats Board -->
        <div class="stats-explorer" id="explorer-stats-container">
            <!-- Populated dynamically -->
        </div>
    `;
    
    // Bind Selector dropdown
    const select = document.getElementById('explorer-feature-select');
    if (select) {
        select.value = selectedFeature;
        select.onchange = (e) => {
            selectedFeature = e.target.value;
            updateStatsAndCharts();
        };
    }
    
    updateStatsAndCharts();
}

function updateStatsAndCharts() {
    const values = rawFeatures.map(f => f[selectedFeature]).filter(v => v !== undefined && v !== null);
    if (values.length === 0) return;
    
    // Calculate statistics
    const sorted = [...values].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const n = sorted.length;
    const mean = values.reduce((sum, v) => sum + v, 0) / n;
    const median = n % 2 !== 0 ? sorted[Math.floor(n / 2)] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
    
    // Std Dev
    const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / n;
    const stdDev = Math.sqrt(variance);
    
    // Render Stats
    const statsContainer = document.getElementById('explorer-stats-container');
    if (statsContainer) {
        statsContainer.innerHTML = `
            <div class="stat-mini-box">
                <div class="stat-label">Minimum</div>
                <div class="stat-mini-val">${min}</div>
            </div>
            <div class="stat-mini-box">
                <div class="stat-label">Maximum</div>
                <div class="stat-mini-val">${max}</div>
            </div>
            <div class="stat-mini-box">
                <div class="stat-label">Mean</div>
                <div class="stat-mini-val">${mean.toFixed(2)}</div>
            </div>
            <div class="stat-mini-box">
                <div class="stat-label">Median</div>
                <div class="stat-mini-val">${median}</div>
            </div>
            <div class="stat-mini-box">
                <div class="stat-label">Std Dev</div>
                <div class="stat-mini-val">${stdDev.toFixed(2)}</div>
            </div>
        `;
    }
    
    // Draw Charts
    drawLineChart(values);
    drawDistChart(values, min, max);
}

function drawLineChart(values) {
    const canvas = document.getElementById('explorer-line-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    canvas.width = width;
    canvas.height = height;
    
    const margin = { top: 20, right: 20, bottom: 20, left: 40 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal === 0 ? 1 : maxVal - minVal;
    
    // Y-axis grid & labels
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = margin.top + (plotHeight * (i / 4));
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(width - margin.right, y);
        ctx.stroke();
        
        const val = maxVal - ((range) * (i / 4));
        ctx.fillStyle = '#8e8e93';
        ctx.font = '9px monospace';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round(val), margin.left - 8, y + 3);
    }
    
    // Draw Train/Test Split Boundary
    const splitIndex = Math.floor(values.length * 0.85); // Matches backend default config
    const splitX = margin.left + (plotWidth * (splitIndex / (values.length - 1)));
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(255, 82, 82, 0.4)';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.moveTo(splitX, margin.top);
    ctx.lineTo(splitX, height - margin.bottom);
    ctx.stroke();
    ctx.setLineDash([]); // Reset
    
    // Draw Split Labels
    ctx.fillStyle = 'rgba(255, 82, 82, 0.7)';
    ctx.font = '9px Inter';
    ctx.textAlign = 'right';
    ctx.fillText('Train', splitX - 8, margin.top + 12);
    ctx.textAlign = 'left';
    ctx.fillText('Test', splitX + 8, margin.top + 12);
    
    // Plot Time-series Line
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(0, 212, 255, 0.75)';
    ctx.lineWidth = 1.5;
    
    values.forEach((v, i) => {
        const x = margin.left + (plotWidth * (i / (values.length - 1)));
        const y = margin.top + plotHeight - (plotHeight * ((v - minVal) / range));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
}

function drawDistChart(values, min, max) {
    const canvas = document.getElementById('explorer-dist-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    canvas.width = width;
    canvas.height = height;
    
    const margin = { top: 20, right: 10, bottom: 20, left: 30 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    
    // Build histogram bins (e.g. 15 bins or 9 digital roots)
    const isDigitalRoot = ['B', 'D', 'F', 'H', 'J', 'L'].includes(selectedFeature);
    const binCount = isDigitalRoot ? 9 : 15;
    const bins = Array(binCount).fill(0);
    const binRange = (max - min) / binCount;
    
    values.forEach(v => {
        let binIdx = 0;
        if (isDigitalRoot) {
            binIdx = Math.max(0, Math.min(8, Math.round(v) - 1));
        } else {
            binIdx = Math.min(binCount - 1, Math.floor((v - min) / (binRange || 1)));
        }
        bins[binIdx]++;
    });
    
    const maxFreq = Math.max(...bins);
    const getX = (idx) => margin.left + (plotWidth * (idx / binCount));
    const binW = (plotWidth / binCount) - 4;
    
    // Draw Bars
    ctx.fillStyle = 'rgba(123, 47, 255, 0.6)';
    bins.forEach((freq, idx) => {
        const x = getX(idx) + 2;
        const h = plotHeight * (freq / (maxFreq || 1));
        const y = margin.top + plotHeight - h;
        
        ctx.fillRect(x, y, binW, h);
        
        // Highlight borders
        ctx.strokeStyle = '#7b2fff';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, binW, h);
        
        // Bin label
        if (idx % 3 === 0 || isDigitalRoot) {
            const labelVal = isDigitalRoot ? idx + 1 : Math.round(min + (idx * binRange));
            ctx.fillStyle = '#8e8e93';
            ctx.font = '8px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(labelVal, x + binW / 2, height - 8);
        }
    });
    
    // Draw vertical frequency grid
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, height - margin.bottom);
    ctx.stroke();
}
