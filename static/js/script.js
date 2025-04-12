const chatContainer = document.getElementById('chat-chat-container');
const logContainer = document.getElementById('log-container');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const loadingDiv = document.getElementById('loading');

let loading = false;
let hasMore = true;
let lastLogTimestamp = null;
const seenLogIds = new Set();

function addMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    messageDiv.innerText = message;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addSystemMessage(message) {
    addMessage(message, 'bot');
}

function addLog(log) {
    if (seenLogIds.has(log.log_id)) return;
    seenLogIds.add(log.log_id);

    const { text, metadata = {} } = log;
    const {
        agent_id = 'N/A',
        timestamp = 'Unknown Time',
        jammed = false,
        communication_quality = 'N/A',
        log_id = '',
    } = metadata;

    const logDiv = document.createElement('div');
    logDiv.className = 'log-message';

    logDiv.innerHTML = `
        <div class="log-header">
            <strong>Agent ${agent_id}</strong>
            <span class="log-time">${new Date(timestamp).toLocaleString()}</span>
        </div>
        <div class="log-body">${text}</div>
        <div class="log-meta">
            <span class="log-id">#${log_id}</span>
            <span class="log-status ${jammed ? 'jammed' : 'clear'}">
                ${jammed ? '🚫 Jammed' : '✅ Clear'}
            </span>
            <span class="log-quality">Comm: ${communication_quality}</span>
        </div>
    `;

    logContainer.appendChild(logDiv);
    logContainer.scrollTop = logContainer.scrollHeight;
}

async function loadLogs() {
    if (loading || !hasMore) return;
    loading = true;
    loadingDiv.textContent = "Loading...";

    try {
        const response = await fetch('/logs');
        const data = await response.json();

        if (Array.isArray(data.logs) && data.logs.length > 0) {
            data.logs.reverse().forEach(log => {
                const time = log?.metadata?.timestamp || 'unknown';
                if (!lastLogTimestamp || new Date(time) > new Date(lastLogTimestamp)) {
                    addLog(log);
                    lastLogTimestamp = time;
                }
            });
        }

        if (!data.has_more) {
            hasMore = false;
            loadingDiv.textContent = "No more logs.";
        } else {
            loadingDiv.textContent = "";
        }
    } catch (e) {
        loadingDiv.textContent = "Error loading logs.";
        console.error("Error while loading logs:", e);
    } finally {
        loading = false;
    }
}

messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    messageInput.value = '';

    const thinkingMessageDiv = document.createElement('div');
    thinkingMessageDiv.className = 'bot-message thinking';
    thinkingMessageDiv.innerText = 'Thinking...';
    chatContainer.appendChild(thinkingMessageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        chatContainer.removeChild(thinkingMessageDiv);

        if (response.ok) {
            const data = await response.json();
            addMessage(data.response, "bot");
            await loadLogs(); // update log section
        } else {
            const error = await response.json();
            addMessage(`Error: ${error.error || 'Unknown error'}`, "bot");
        }
    } catch (error) {
        chatContainer.removeChild(thinkingMessageDiv);
        addMessage("Network error. Please try again.", "bot");
        console.error("Chat error:", error);
    }
});

// Initial welcome message
document.addEventListener('DOMContentLoaded', () => {
    addSystemMessage("Welcome to the RAG Demo! Enter a message to start chatting.");
    loadLogs();
});