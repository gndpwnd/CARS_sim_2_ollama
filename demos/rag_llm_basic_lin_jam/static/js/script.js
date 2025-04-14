const chatContainer = document.getElementById('chat-chat-container');
const logContainer = document.getElementById('log-container');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const loadingDiv = document.getElementById('loading');

let loading = false;
let lastLogTimestamp = null;
const seenLogIds = new Set();

// Utility: Create a div with classes and inner text
function createDiv(classes = [], text = '') {
    const div = document.createElement('div');
    div.classList.add(...classes);
    if (text) div.innerText = text;
    return div;
}

// Chat UI
function addMessage(message, type = 'bot') {
    const messageDiv = createDiv([`${type}-message`], message);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Log UI
function addLog(log) {
    if (seenLogIds.has(log.log_id)) return;
    seenLogIds.add(log.log_id);

    const { text, metadata = {} } = log;
    const {
        agent_id = 'N/A',
        role = 'system',
        timestamp = new Date().toISOString(),
        jammed = null,
        communication_quality = '',
        log_id = ''
    } = metadata;

    const logDiv = createDiv(['log-message']);
    if (role === 'user') logDiv.classList.add('user-log');
    if (role === 'ollama') logDiv.classList.add('ollama-log');

    logDiv.innerHTML = `
        <div class="log-header">
            <strong>${role || agent_id}</strong>
            <span class="log-time">${new Date(timestamp).toLocaleString()}</span>
        </div>
        <div class="log-body">${text}</div>
        <div class="log-meta">
            ${log_id ? `<span class="log-id">#${log_id}</span>` : ''}
            ${jammed !== null ? `<span class="log-status ${jammed ? 'jammed' : 'clear'}">
                ${jammed ? '🚫 Jammed' : '✅ Clear'}
            </span>` : ''}
            ${communication_quality ? `<span class="log-quality">Comm: ${communication_quality}</span>` : ''}
        </div>
    `;

    logContainer.prepend(logDiv);
    logContainer.scrollTop = 0; // Always scroll to top
}


// Log Fetcher
async function loadLogs() {
    if (loading) return;
    loading = true;
    loadingDiv.textContent = "Loading logs...";

    try {
        const response = await fetch('/logs');
        const { logs = [], has_more = false } = await response.json();
        console.log("Logs:", logs);


        if (logs.length) {
            logContainer.innerHTML = '';
            seenLogIds.clear();
            logs.reverse().forEach(addLog);  // Reverse here
        }

        loadingDiv.textContent = has_more ? "Load more..." : "No more logs.";
    } catch (e) {
        console.error("Error loading logs:", e);
        loadingDiv.textContent = "Error loading logs.";
    } finally {
        loading = false;
    }
}

// Live Polling
function startLivestream(interval = 3000) {
    setInterval(async () => {
        if (loading) return;

        try {
            const response = await fetch('/logs');
            const { logs = [] } = await response.json();

            logs.forEach(log => {
                const logTime = new Date(log?.metadata?.timestamp || 0);
                if (!lastLogTimestamp || logTime > new Date(lastLogTimestamp)) {
                    addLog(log);
                    lastLogTimestamp = log.metadata.timestamp;
                }
            });
        } catch (err) {
            console.error("Live update failed:", err);
        }
    }, interval);
}

// Chat Submit
messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    messageInput.value = '';

    const thinking = createDiv(['bot-message', 'thinking'], 'Thinking...');
    chatContainer.appendChild(thinking);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        thinking.remove();

        if (res.ok) {
            const { response } = await res.json();
            addMessage(response, 'bot');
            setTimeout(loadLogs, 500);
        } else {
            const { error } = await res.json();
            addMessage(`Error: ${error || 'Unknown error'}`, 'bot');
        }
    } catch (err) {
        thinking.remove();
        addMessage("Network error. Please try again.", 'bot');
    }
});

// Initial load and stream
window.addEventListener('DOMContentLoaded', () => {
    loadLogs();
    startLivestream();
});
