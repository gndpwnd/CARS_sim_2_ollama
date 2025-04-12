const chatContainer = document.getElementById('chat-chat-container');
const logContainer = document.getElementById('log-container');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const loadingDiv = document.getElementById('loading');

let loading = false;
let hasMore = true;
let lastLogTimestamp = null; // Keep track of last log timestamp displayed

// Function to add messages to chat container
function addMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    messageDiv.innerText = message;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Function to add logs to log container
function addLog(message) {
    const logDiv = document.createElement('div');
    logDiv.className = 'log-message';
    logDiv.innerText = message;
    logContainer.appendChild(logDiv);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Function to load latest logs

async function loadLogs() {
    if (loading || !hasMore) return;
    loading = true;
    loadingDiv.textContent = "Loading...";

    try {
        const response = await fetch('/logs');
        const data = await response.json();

        console.log("Logs response:", data);

        if (Array.isArray(data.logs) && data.logs.length > 0) {
            data.logs.reverse().forEach(log => {
                const role = log?.metadata?.role || 'unknown';
                const time = log?.metadata?.timestamp || 'unknown time';

                // Only add logs newer than the latest we've seen
                if (!lastLogTimestamp || new Date(time) > new Date(lastLogTimestamp)) {
                    addLog(`${role} (${time}): ${log.text}`);
                    lastLogTimestamp = time;  // update the latest timestamp seen
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


// Handle message form submit (user chatting)
messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    messageInput.value = '';

    const thinkingMessageDiv = document.createElement('div');
    thinkingMessageDiv.className = 'bot-message thinking';
    thinkingMessageDiv.innerText = 'Thinking';
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
            await loadLogs();  // ✅ Reload logs after bot responds
        } else {
            const error = await response.json();
            addMessage(`Error: ${error.error || 'Unknown error'}`, "bot");
        }
    } catch (error) {
        chatContainer.removeChild(thinkingMessageDiv);
        addMessage(`Error: ${error.message}`, "bot");
    }

    chatContainer.scrollTop = chatContainer.scrollHeight;
});

// Initial load of logs when the page loads
loadLogs();

// ✅ Periodically poll for new logs every 5 seconds
setInterval(loadLogs, 5000);
