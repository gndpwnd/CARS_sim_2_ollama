const chatContainer = document.getElementById('chat-chat-container');
const logContainer = document.getElementById('log-container');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const loadingDiv = document.getElementById('loading');

let loading = false;
let hasMore = true;
let lastLogTimestamp = null;
let totalLogs = 0; // Track total number of logs
const seenLogIds = new Set();

// Function to add a message to the chat
function addMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    messageDiv.innerText = message;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Function to add a system message
function addSystemMessage(message) {
    addMessage(message, 'bot');
}

// Function to add log to log container
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

// Fetch the current number of logs
async function getLogCount() {
    try {
        const response = await fetch('/logs/count');
        const data = await response.json();
        totalLogs = data.count || 0; // Store the total logs count
    } catch (e) {
        console.error("Error fetching log count:", e);
    }
}

// Fetch a specific log by its index
async function getLogByNumber(logNumber) {
    try {
        const response = await fetch(`/logs/${logNumber}`);
        const data = await response.json();
        if (data.log) {
            addLog(data.log); // Add the log to the container
        } else {
            console.error(`Log with number ${logNumber} not found.`);
        }
    } catch (e) {
        console.error("Error fetching specific log:", e);
    }
}

// Livestream function to show the most recent logs
async function startLivestream() {
    setInterval(async () => {
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
    }, 3000); // Update every 3 seconds
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
document.addEventListener('DOMContentLoaded', async () => {
    addSystemMessage("Welcome to the RAG Demo! Enter a message to start chatting.");
    await getLogCount(); // Get total log count on page load
    loadLogs(); // Load logs initially
    startLivestream(); // Start livestream updates
});
