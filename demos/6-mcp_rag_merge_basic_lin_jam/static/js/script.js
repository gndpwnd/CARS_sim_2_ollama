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
        logContainer.scrollTop = 0; // Always scroll to top
    }

    // Log Fetcher - Load all logs at once
    async function loadLogs() {
        if (loading) return;
        loading = true;
        loadingDiv.textContent = "Loading logs...";

        try {
            const response = await fetch('/logs');
            const data = await response.json();
            
            if (!data.logs) {
                console.error("Missing logs in response:", data);
                loadingDiv.textContent = "Error: Invalid log data";
                return;
            }
            
            const logs = data.logs;
            console.log(`Loaded ${logs.length} logs for RAG feed`);

            if (logs.length) {
                // Clear existing logs
                logContainer.innerHTML = '';
                seenLogIds.clear();
                
                // Add all logs in reverse chronological order
                logs.forEach(log => {
                    addLog(log);
                    
                    // Track this log ID
                    seenLogIds.add(log.log_id);
                    
                    // Keep track of the most recent timestamp
                    const timestamp = log?.metadata?.timestamp;
                    if (timestamp && (!lastLogTimestamp || new Date(timestamp) > new Date(lastLogTimestamp))) {
                        lastLogTimestamp = timestamp;
                    }
                });
                
                console.log("Logs loaded successfully. Latest timestamp:", lastLogTimestamp);
            }

            loadingDiv.textContent = `${logs.length} logs loaded.`;
        } catch (e) {
            console.error("Error loading logs:", e);
            loadingDiv.textContent = "Error loading logs.";
        } finally {
            loading = false;
        }
    }

    // MCP Command Sender - NEW FUNCTIONALITY
    async function sendMcpCommand(command) {
        try {
            console.log("Sending MCP command:", command);
            const response = await fetch('/llm_command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: command })
            });
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log("MCP command response:", data);
            
            if (data.results && data.results.length > 0) {
                // Display results in chat
                const resultsStr = data.results.map(r => 
                    r.success ? 
                    `✅ ${r.message || `Moving ${r.agent} to (${r.x}, ${r.y})`}` : 
                    `❌ ${r.message || 'Command not understood'}`
                ).join('\n');
                
                addMessage(`Command processed:\n${resultsStr}`, 'bot');
                
                // Refresh logs after command execution
                setTimeout(loadLogs, 500);
                return data;
            } else {
                throw new Error("Invalid response format");
            }
        } catch (err) {
            console.error("MCP command error:", err);
            addMessage(`Error executing command: ${err.message}`, 'bot');
            return null;
        }
    }

    // Improved chat submission with better error handling
    messageForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userInput = messageInput.value.trim();
        if (!userInput) return;

        // Show user message immediately
        addMessage(userInput, 'user');
        messageInput.value = '';
        
        // Add loading indicator
        const loadingIndicator = document.createElement('div');
        loadingIndicator.classList.add('bot-message', 'loading');
        loadingIndicator.innerText = 'Thinking...';
        chatContainer.appendChild(loadingIndicator);
        
        // Check if this might be a movement command
        const moveKeywords = ['move', 'go', 'place', 'put', 'send', 'position'];
        const isMoveCommand = moveKeywords.some(keyword => 
            userInput.toLowerCase().includes(keyword)
        );
        
        try {
            // If it looks like a movement command, try MCP first
            if (isMoveCommand) {
                try {
                    // Attempt to process as MCP command
                    const mcpResult = await sendMcpCommand(userInput);
                    
                    // If successfully processed as movement, remove loading and return
                    if (mcpResult && mcpResult.results && mcpResult.results.some(r => r.success)) {
                        // Remove loading indicator
                        chatContainer.removeChild(loadingIndicator);
                        return;
                    }
                    // Otherwise fall through to regular chat processing
                } catch (mcpErr) {
                    console.log("Not a valid MCP command, falling back to chat:", mcpErr);
                    // Continue to regular chat processing
                }
            }
            
            // Process as regular chat message
            console.log("Sending chat request with:", userInput);
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: userInput })
            });

            // Remove loading indicator
            chatContainer.removeChild(loadingIndicator);
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log("Received response data:", data);
            
            if (data.error) {
                console.error("Server error:", data.error);
                addMessage(`Error: ${data.error}`, 'bot');
                return;
            }

            // Show the bot response
            const botReply = data.response || "No response received.";
            addMessage(botReply, 'bot');
            
            // Refresh the log list to include new chat messages
            setTimeout(loadLogs, 500);
            
        } catch (err) {
            console.error("Chat error:", err);
            
            // Remove loading indicator if still there
            if (loadingIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(loadingIndicator);
            }
            
            addMessage(`Error: ${err.message || "Could not contact the server."}`, 'bot');
        }
    });

    // Log polling function - reload all logs periodically
    function startLogPolling(interval = 5000) {
        console.log(`Starting log polling every ${interval}ms`);
        setInterval(() => {
            if (!loading) {
                console.log("Reloading logs...");
                loadLogs();
            }
        }, interval);
    }

    // Initial load and stream
    loadLogs();
    startLogPolling();
});