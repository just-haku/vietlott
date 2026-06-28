/**
 * SOUL · AI Response Feed Module
 * Displays dynamic live feed of LLM suggestions, code snippets,
 * and handles custom direct testing inputs.
 */

import { api, subscribe, showToast } from './app.js';

let container = null;
let feedList = [];

export async function init(targetElement) {
    container = targetElement;
    render();
    
    // Subscribe to SSE updates
    subscribe('sse-event', (event) => {
        if (event.type === 'ai_response') {
            feedList.push(event.data);
            appendFeedItem(event.data);
        }
    });
}

function render() {
    container.innerHTML = `
        <div class="feed-list" id="ai-feed-container">
            <div class="info-empty">
                🤖 AI Response Feed is active. When the auto-research agent runs, its detailed mathematical reasoning and code changes will stream here in real time.
            </div>
        </div>
        
        <!-- Direct Prompt Testing Area -->
        <div class="direct-test-box" style="margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); padding-top:16px;">
            <div class="form-group" style="margin-bottom:8px;">
                <label style="font-size:0.75rem; color:var(--text-muted);">Direct Model Tester</label>
                <textarea id="ai-test-prompt" class="text-input" placeholder="Type a custom prompt to test model generation..." style="min-height:50px; resize:vertical; font-family:var(--font-sans); padding:8px 12px; font-size:0.85rem;"></textarea>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.75rem; color:var(--text-muted);" id="tester-model-info">Model: Gemma 4</span>
                <button id="btn-test-submit" class="btn btn-primary" style="padding:6px 12px; font-size:0.8rem; border-radius:6px;">
                    Send Test
                </button>
            </div>
        </div>
    `;
    
    const submitBtn = document.getElementById('btn-test-submit');
    const promptInput = document.getElementById('ai-test-prompt');
    
    submitBtn.onclick = async () => {
        const promptVal = promptInput.value.trim();
        if (!promptVal) return;
        
        submitBtn.disabled = true;
        submitBtn.innerText = 'Generating...';
        showToast('Sending prompt to LLM pool...', 'info');
        
        try {
            const res = await api.post('/api/llm/generate', {
                prompt: promptVal,
                system_prompt: "You are an expert AI software engineer and ML researcher investigating lottery determinism."
            });
            
            showToast('Generation complete', 'success');
            promptInput.value = '';
            
            // Note: The backend also pushes to SSE, which will render it.
            // If it is not pushed to SSE, we render manually here.
            if (res && res.response) {
                // If it is not in the feed, push it.
                if (!feedList.some(item => item.timestamp === res.timestamp)) {
                    feedList.push(res);
                    appendFeedItem(res);
                }
            }
        } catch (err) {
            showToast(`Generation failed: ${err.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = 'Send Test';
        }
    };
}

function appendFeedItem(data) {
    const listContainer = document.getElementById('ai-feed-container');
    if (!listContainer) return;
    
    // Clear placeholder
    const emptyMsg = listContainer.querySelector('.info-empty');
    if (emptyMsg) emptyMsg.remove();
    
    const dateStr = new Date(data.timestamp).toLocaleTimeString();
    
    const feedCard = document.createElement('div');
    feedCard.className = 'feed-item';
    feedCard.style.marginTop = '12px';
    
    // Basic formatting for Markdown blocks (mostly pre/code blocks)
    let formattedResponse = data.response;
    
    // Format JSON/JSON blocks
    formattedResponse = formattedResponse.replace(/```json\s*([\s\S]*?)```/g, '<pre><code class="language-json">$1</code></pre>');
    formattedResponse = formattedResponse.replace(/```python\s*([\s\S]*?)```/g, '<pre><code class="language-python">$1</code></pre>');
    formattedResponse = formattedResponse.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    feedCard.innerHTML = `
        <div class="feed-header">
            <span>🤖 Model Response (${data.provider}/${data.model})</span>
            <span>${dateStr}</span>
        </div>
        <div class="feed-content">
            <div style="font-weight:600; color:var(--primary); margin-bottom:6px; font-size:0.8rem;">
                Prompt excerpt: "${data.prompt.substring(0, 100)}..."
            </div>
            <div>${formattedResponse}</div>
        </div>
    `;
    
    listContainer.appendChild(feedCard);
    
    // Handle Autoscroll lock
    const scrollLock = document.getElementById('ai-scroll-lock');
    if (scrollLock && scrollLock.checked) {
        listContainer.scrollTop = listContainer.scrollHeight;
    }
}
