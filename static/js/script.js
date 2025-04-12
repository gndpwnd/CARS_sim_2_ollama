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
        role = 'N/A',
        timestamp = 'Unknown Time',
        jammed = false,
        communication_quality = 'N/A',
        log_id = '',
    } = metadata;

    const logDiv = document.createElement('div');
    logDiv.className = 'log-message';
    if (role === 'user') {
        logDiv.classList.add('user-log');
    } else if (role === 'ollama') {
        logDiv.classList.add('ollama-log');
    }

    logDiv.innerHTML = `
        <div class="log-header">
            <strong>${role || agent_id}</strong>
            <span class="log-time">${new Date(timestamp).toLocaleString()}</span>
        </div>
        <div class="log-body">${text}</div>
        <div class="log-meta">
            <span class="log-id">#${log_id}</span>
            ${jammed !== undefined ? `
                <span class="log-status ${jammed ? 'jammed' : 'clear'}">
                    ${jammed ? '🚫 Jammed' : '✅ Clear'}
                </span>
            ` : ''}
            ${communication_quality ? `<span class="log-quality">Comm: ${communication_quality}</span>` : ''}
        </div>
    `;

    logContainer.appendChild(logDiv);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Fetch the current number of logs
async function getLogCount() {
    try {
        // Use the correct route matching your Flask backend
        const response = await fetch('/log_count');
        const data = await response.json();
        totalLogs = data.log_count || 0; // Match the field name from your Flask route
        console.log(`Total logs: ${totalLogs}`);
    } catch (e) {
        console.error("Error fetching log count:", e);
    }
}

// Load logs function - this was missing in your original code
async function loadLogs() {
    if (loading) return;
    loading = true;
    
    if (loadingDiv) {
        loadingDiv.textContent = "Loading logs...";
    }

    try {
        const response = await fetch('/logs');
        const data = await response.json();

        if (Array.isArray(data.logs) && data.logs.length > 0) {
            // Clear existing logs if needed
            // logContainer.innerHTML = '';
            
            data.logs.forEach(log => {
                addLog(log);
                if (log?.metadata?.timestamp) {
                    const logTime = new Date(log.metadata.timestamp);
                    if (!lastLogTimestamp || logTime > new Date(lastLogTimestamp)) {
                        lastLogTimestamp = log.metadata.timestamp;
                    }
                }
            });
            
            hasMore = data.has_more;
        } else {
            console.log("No logs found or empty data returned");
        }
        
        if (loadingDiv) {
            loadingDiv.textContent = hasMore ? "" : "No more logs.";
        }
    } catch (e) {
        console.error("Error loading logs:", e);
        if (loadingDiv) {
            loadingDiv.textContent = "Error loading logs.";
        }
    } finally {
        loading = false;
    }
}

// Fetch a specific log chunk
async function getLogChunk(chunkNum) {
    try {
        const response = await fetch(`/log_chunk/${chunkNum}`);
        const data = await response.json();
        if (Array.isArray(data.logs) && data.logs.length > 0) {
            data.logs.forEach(log => addLog(log));
            hasMore = data.has_more;
        }
    } catch (e) {
        console.error(`Error fetching log chunk ${chunkNum}:`, e);
    }
}

// Livestream function to show the most recent logs
async function startLivestream() {
    setInterval(async () => {
        if (loading) return;
        
        try {
            await getLogCount(); // Update the log count
            
            // Only fetch new logs if we're not already loading
            const response = await fetch('/logs');
            const data = await response.json();

            if (Array.isArray(data.logs) && data.logs.length > 0) {
                data.logs.forEach(log => {
                    const time = log?.metadata?.timestamp || 'unknown';
                    if (!lastLogTimestamp || new Date(time) > new Date(lastLogTimestamp)) {
                        addLog(log);
                        lastLogTimestamp = time;
                    }
                });
            }
        } catch (e) {
            console.error("Error during livestream update:", e);
        }
    }, 3000); // Update every 3 seconds
}

messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    messageInput.value = '';

    // Create a temporary "thinking" message
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

        // Remove the thinking message if it exists
        if (thinkingMessageDiv && thinkingMessageDiv.parentNode === chatContainer) {
            chatContainer.removeChild(thinkingMessageDiv);
        }

        if (response.ok) {
            const data = await response.json();
            addMessage(data.response, "bot");
            
            // Delay loading logs to ensure they've been updated in the backend
            setTimeout(() => loadLogs(), 500);
        } else {
            const error = await response.json();
            addMessage(`Error: ${error.error || 'Unknown error'}`, "bot");
        }
    } catch (error) {
        // Remove the thinking message if it exists and hasn't been removed yet
        if (thinkingMessageDiv && thinkingMessageDiv.parentNode === chatContainer) {
            chatContainer.removeChild(thinkingMessageDiv);
        }
        
        addMessage("Network error. Please try again.", "bot");
        console.error("Chat error:", error);
    }
});

// Initial welcome message
document.addEventListener('DOMContentLoaded', async () => {
    // Check if elements exist before using them
    if (chatContainer) {
        addSystemMessage("Welcome to the RAG Demo! Enter a message to start chatting.");
    } else {
        console.error("Chat container element not found!");
    }
    
    await getLogCount(); // Get total log count on page load
    await loadLogs(); // Load logs initially
    startLivestream(); // Start livestream updates
});