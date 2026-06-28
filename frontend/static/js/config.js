/**
 * SOUL · Engine Configuration Module
 * Manages configuration updates, LLM pool settings, and saves to server.
 */

import { api, showToast } from './app.js';

let container = null;

export async function init(targetElement) {
    container = targetElement;
    await render();
}

async function render() {
    container.innerHTML = `
        <div class="skeleton-loader">
            <div class="skeleton-line"></div>
        </div>
    `;
    
    try {
        const config = await api.get('/api/config');
        
        container.innerHTML = `
            <form id="config-form" class="config-form">
                <div class="form-row" style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
                    <div class="form-group">
                        <label for="provider-select">LLM Provider</label>
                        <select id="provider-select" class="select-input">
                            <option value="google" ${config.provider === 'google' ? 'selected' : ''}>Google Gemini</option>
                            <option value="groq" ${config.provider === 'groq' ? 'selected' : ''}>Groq API</option>
                            <option value="deepseek" ${config.provider === 'deepseek' ? 'selected' : ''}>DeepSeek API</option>
                            <option value="openai" ${config.provider === 'openai' ? 'selected' : ''}>OpenAI API</option>
                            <option value="anthropic" ${config.provider === 'anthropic' ? 'selected' : ''}>Anthropic API</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="model-input">Model Name</label>
                        <input type="text" id="model-input" class="text-input" value="${config.model || 'gemma-4-27b-it'}" placeholder="e.g. gemma-4-27b-it">
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="key-input">API Secret Key (Masked)</label>
                    <input type="password" id="key-input" class="text-input" value="${config.api_key || ''}" placeholder="••••••••••••••••••••••••">
                </div>
                
                <div class="form-row" style="display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:center;">
                    <div class="form-group">
                        <label for="temp-slider">Temperature</label>
                        <div class="range-group">
                            <input type="range" id="temp-slider" class="range-input" min="0" max="1" step="0.05" value="${config.temperature ?? 0.7}">
                            <span id="temp-val" class="range-val">${config.temperature ?? 0.7}</span>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="split-slider">Train Split %</label>
                        <div class="range-group">
                            <input type="range" id="split-slider" class="range-input" min="0.5" max="0.95" step="0.05" value="${config.train_split ?? 0.85}">
                            <span id="split-val" class="range-val">${Math.round((config.train_split ?? 0.85) * 100)}%</span>
                        </div>
                    </div>
                </div>
                
                <button type="submit" id="btn-save-config" class="btn btn-primary" style="margin-top: 12px; width:100%; justify-content:center;">
                    Save Configuration
                </button>
            </form>
        `;
        
        // Handle input live previews
        const tempSlider = document.getElementById('temp-slider');
        const tempVal = document.getElementById('temp-val');
        tempSlider.oninput = () => tempVal.innerText = tempSlider.value;
        
        const splitSlider = document.getElementById('split-slider');
        const splitVal = document.getElementById('split-val');
        splitSlider.oninput = () => splitVal.innerText = `${Math.round(splitSlider.value * 100)}%`;
        
        // Handle save
        const form = document.getElementById('config-form');
        form.onsubmit = async (e) => {
            e.preventDefault();
            
            const submitBtn = document.getElementById('btn-save-config');
            submitBtn.disabled = true;
            submitBtn.innerText = 'Saving...';
            
            const newConfig = {
                provider: document.getElementById('provider-select').value,
                model: document.getElementById('model-input').value.trim(),
                api_key: document.getElementById('key-input').value.trim(),
                temperature: parseFloat(tempSlider.value),
                train_split: parseFloat(splitSlider.value)
            };
            
            try {
                const res = await api.post('/api/config', newConfig);
                if (res.status === 'ok') {
                    showToast('Configuration persisted successfully!', 'success');
                    
                    // Update model name info in UI if applicable
                    const modelInfoText = document.getElementById('tester-model-info');
                    if (modelInfoText) {
                        modelInfoText.innerText = `Model: ${newConfig.model}`;
                    }
                }
            } catch (err) {
                showToast(`Failed to save config: ${err.message}`, 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerText = 'Save Configuration';
            }
        };
        
    } catch (err) {
        container.innerHTML = `<div class="error-msg">⚠️ Failed to load configuration settings.</div>`;
    }
}
