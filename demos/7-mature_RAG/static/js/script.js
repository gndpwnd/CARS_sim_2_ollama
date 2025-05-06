// Global state
let loading = false;
let lastLogTimestamp = null;
const seenLogIds = new Set();

// DOM elements
document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-chat-container');
    const logContainer = document.getElementById('log-container');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const loadingDiv = document.getElementById('loading');

    // Utility: Create a div with classes and inner text
    function createDiv(classes = [], text = '') {
        const div = document.createElement('div');
        div.classList.add(...classes);
        div.innerText = String(text);  // force string conversion
        return div;
    }

    // Enhanced message display with status indicators
    function addMessage(message, type = 'bot', status = '') {
        const messageDiv = createDiv([`${type}-message`], message);
        if (status) {
            messageDiv.classList.add(`message-${status}`);
            const statusIndicator = document.createElement('span');
            statusIndicator.className = 'status-indicator';
            statusIndicator.textContent = status === 'success' ? '✓' : '✗';
            messageDiv.prepend(statusIndicator);
        }
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return messageDiv;
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
            position = '',
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
                ${position ? `<span class="log-position">@ ${position}</span>` : ''}
                ${log_id ? `<span class="log-id">#${log_id}</span>` : ''}
                ${jammed !== null ? `<span class="log-status ${jammed ? 'jammed' : 'clear'}">
                    ${jammed ? '🚫 Jammed' : '✅ Clear'}
                </span>` : ''}
                ${communication_quality ? `<span class="log-quality">Comm: ${communication_quality}</span>` : ''}
            </div>
        `;

        logContainer.prepend(logDiv);
        logContainer.scrollTop = 0;
    }

    // Enhanced log loading with better error feedback
    async function loadLogs() {
        if (loading) return;
        loading = true;
        loadingDiv.textContent = "Loading logs...";
        loadingDiv.classList.add('loading-active');

        try {
            const response = await fetch('/logs');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            if (!data?.logs) {
                throw new Error("Invalid log data format");
            }
            
            console.log(`Loaded ${data.logs.length} logs for RAG feed`);

            if (data.logs.length) {
                // Clear existing logs only if we have new ones
                logContainer.innerHTML = '';
                seenLogIds.clear();
                
                data.logs.forEach(log => {
                    addLog(log);
                    seenLogIds.add(log.log_id);
                    
                    const timestamp = log?.metadata?.timestamp;
                    if (timestamp && (!lastLogTimestamp || new Date(timestamp) > new Date(lastLogTimestamp))) {
                        lastLogTimestamp = timestamp;
                    }
                });
                
                loadingDiv.textContent = `Loaded ${data.logs.length} logs. Latest: ${new Date(lastLogTimestamp).toLocaleTimeString()}`;
            } else {
                loadingDiv.textContent = "No new logs available";
            }
        } catch (e) {
            console.error("Error loading logs:", e);
            loadingDiv.textContent = `Error: ${e.message}`;
            loadingDiv.classList.add('error');
            setTimeout(() => loadingDiv.classList.remove('error'), 2000);
        } finally {
            loadingDiv.classList.remove('loading-active');
            loading = false;
        }
    }


    async function sendCommand(command) {
        try {
            console.log("Sending command:", command);
            const response = await fetch('/llm_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: command })
            });
    
            const data = await response.json();
            console.log("Full response:", data);
    
            // Use actual response with fallback
            const responseText = data?.response?.trim() || "No response received.";
    
            return {
                success: !!data?.response?.trim(),
                message: responseText,
                raw: data,
                liveData: data?.live_data || null  // Include live data in return
            };
    
        } catch (err) {
            return {
                success: false,
                message: err.message || "Command failed",
                error: err
            };
        }
    }
    
    messageForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userInput = messageInput.value.trim();
        if (!userInput) return;
    
        // Show user message
        addMessage(userInput, 'user');
        messageInput.value = '';
        
        // Show loading
        const loadingIndicator = addMessage("Processing...", 'bot', 'loading');
    
        try {
            const { success, message, raw, liveData } = await sendCommand(userInput);
            
            // Remove loading
            if (loadingIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(loadingIndicator);
            }
    
            let style = 'success';
            if (!success || message.includes('Error') || message.includes('not found') || message.includes('Invalid')) {
                style = 'error';
            } else if (message === "Not a movement command") {
                style = 'info';
            }
    
            // Show formatted response
            const responseDiv = addMessage(message, 'bot', style);
            
            // Add live data visualization if available
            if (liveData) {
                const liveDataDiv = createDiv(['live-data-container']);
                
                Object.entries(liveData).forEach(([agentId, data]) => {
                    if (data) {
                        const agentDiv = createDiv(['live-agent-data']);
                        agentDiv.innerHTML = `
                            <strong>${agentId}</strong>:
                            Position (${data.x?.toFixed(2)}, ${data.y?.toFixed(2)})
                            | Comm: ${(data.communication_quality * 100).toFixed(0)}%
                            | ${data.jammed ? '🚫 Jammed' : '✅ Clear'}
                        `;
                        liveDataDiv.appendChild(agentDiv);
                    }
                });
                
                responseDiv.appendChild(liveDataDiv);
            }
    
            // Refresh logs
            setTimeout(loadLogs, 1000);
    
        } catch (err) {
            console.error("Error:", err);
            if (loadingIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(loadingIndicator);
            }
            addMessage(`Error: ${err.message}`, 'bot', 'error');
        }
    });
    

    // Log polling with backoff on errors
    function startLogPolling() {
        const pollInterval = 3000;
        
        const poll = async () => {
            if (loading) {
                setTimeout(poll, pollInterval);
                return;
            }
            
            try {
                await loadLogs();
            } catch (e) {
                console.error("Polling error:", e);
            } finally {
                setTimeout(poll, pollInterval);
            }
        };
        
        console.log(`Starting log polling every ${pollInterval}ms`);
        poll();
    }

    // Initial load
    loadLogs();
    startLogPolling();
});