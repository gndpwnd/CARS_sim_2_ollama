// Multi-Source Dashboard JavaScript - Fixed Version
(function() {
    'use strict';

    // State Management
    const state = {
        postgresql: {
            logs: new Set(),
            streaming: false,
            eventSource: null,
            container: null,
            toggle: null,
            count: 0
        },
        qdrant: {
            logs: new Set(),
            streaming: false,
            eventSource: null,
            container: null,
            toggle: null,
            count: 0
        },
        chat: {
            container: null,
            form: null,
            input: null
        }
    };

    // Initialize on DOM load
    document.addEventListener('DOMContentLoaded', init);

    function init() {
        console.log('[INIT] Starting dashboard initialization...');
        
        // Get DOM elements
        state.postgresql.container = document.getElementById('postgresql-container');
        state.postgresql.toggle = document.getElementById('pg-stream-toggle');
        state.qdrant.container = document.getElementById('qdrant-container');
        state.qdrant.toggle = document.getElementById('qdrant-stream-toggle');
        state.chat.container = document.getElementById('chat-container');
        state.chat.form = document.getElementById('message-form');
        state.chat.input = document.getElementById('message-input');

        // Verify all elements exist
        if (!state.postgresql.container || !state.postgresql.toggle) {
            console.error('[ERROR] PostgreSQL elements not found');
            return;
        }
        if (!state.qdrant.container || !state.qdrant.toggle) {
            console.error('[ERROR] Qdrant elements not found');
            return;
        }
        if (!state.chat.container || !state.chat.form || !state.chat.input) {
            console.error('[ERROR] Chat elements not found');
            return;
        }

        console.log('[INIT] All DOM elements found');

        // Setup event listeners
        setupEventListeners();

        // Initial data load
        loadInitialData();

        // Check system health immediately and then periodically
        checkSystemHealth();
        setInterval(checkSystemHealth, 10000); // Every 10 seconds
    }

    function setupEventListeners() {
        console.log('[INIT] Setting up event listeners...');
        
        // PostgreSQL stream toggle
        state.postgresql.toggle.addEventListener('click', () => {
            toggleStream('postgresql');
        });

        // Qdrant stream toggle
        state.qdrant.toggle.addEventListener('click', () => {
            toggleStream('qdrant');
        });

        // Chat form submission
        state.chat.form.addEventListener('submit', handleChatSubmit);

        // Clear chat button
        const clearChatBtn = document.getElementById('clear-chat');
        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', () => {
                const welcomeMsg = state.chat.container.querySelector('.welcome-message');
                state.chat.container.innerHTML = '';
                if (welcomeMsg) {
                    state.chat.container.appendChild(welcomeMsg);
                }
                addChatMessage('Chat cleared', 'bot');
            });
        }
    }

    async function loadInitialData() {
        console.log('[INIT] Loading initial data...');
        
        // Load PostgreSQL data
        try {
            const response = await fetch('/data/postgresql');
            const data = await response.json();
            
            if (data.logs && data.logs.length > 0) {
                console.log(`[PostgreSQL] Loaded ${data.logs.length} initial logs`);
                // Clear empty state
                state.postgresql.container.innerHTML = '';
                data.logs.reverse().forEach(log => addLog('postgresql', log));
                updateCount('postgresql', state.postgresql.logs.size);
            }
        } catch (error) {
            console.error('[PostgreSQL] Failed to load initial data:', error);
            updateLoadingStatus('postgresql', 'Failed to load initial data', true);
        }

        // Load Qdrant data
        try {
            const response = await fetch('/data/qdrant');
            const data = await response.json();
            
            if (data.logs && data.logs.length > 0) {
                console.log(`[Qdrant] Loaded ${data.logs.length} initial logs`);
                // Clear empty state
                state.qdrant.container.innerHTML = '';
                data.logs.reverse().forEach(log => addLog('qdrant', log));
                updateCount('qdrant', state.qdrant.logs.size);
            }
        } catch (error) {
            console.error('[Qdrant] Failed to load initial data:', error);
            updateLoadingStatus('qdrant', 'Failed to load initial data', true);
        }

        // Auto-start streaming after a delay
        setTimeout(() => {
            console.log('[INIT] Auto-starting streams...');
            startStream('postgresql');
            startStream('qdrant');
        }, 1000);
    }

    function toggleStream(source) {
        const streamState = state[source];
        
        if (streamState.streaming) {
            stopStream(source);
        } else {
            startStream(source);
        }
    }

    function startStream(source) {
        const streamState = state[source];
        const endpoint = `/stream/${source}`;

        console.log(`[${source.toUpperCase()}] Starting stream from ${endpoint}...`);
        
        // Close existing connection if any
        if (streamState.eventSource) {
            streamState.eventSource.close();
        }
        
        streamState.eventSource = new EventSource(endpoint);
        streamState.streaming = true;
        
        // Update button
        streamState.toggle.classList.add('active');
        const icon = streamState.toggle.querySelector('.stream-icon');
        if (icon) icon.textContent = '🟢';
        streamState.toggle.innerHTML = '<span class="stream-icon">🟢</span> Live';

        // Handle incoming messages
        streamState.eventSource.onmessage = (event) => {
            try {
                const log = JSON.parse(event.data);
                addLog(source, log);
                updateCount(source, streamState.logs.size);
            } catch (error) {
                console.error(`[${source.toUpperCase()}] Error parsing stream data:`, error);
            }
        };

        // Handle errors
        streamState.eventSource.onerror = (error) => {
            console.error(`[${source.toUpperCase()}] Stream error:`, error);
            updateLoadingStatus(source, '⚠️ Stream disconnected, retrying...', true);
            
            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                if (streamState.streaming) {
                    console.log(`[${source.toUpperCase()}] Attempting reconnect...`);
                    stopStream(source);
                    setTimeout(() => startStream(source), 1000);
                }
            }, 3000);
        };

        // Handle open
        streamState.eventSource.onopen = () => {
            console.log(`[${source.toUpperCase()}] Stream connected`);
            updateLoadingStatus(source, '🟢 Live streaming', false);
            updateStatusIndicator(source, 'online');
        };
    }

    function stopStream(source) {
        const streamState = state[source];
        
        console.log(`[${source.toUpperCase()}] Stopping stream...`);
        
        if (streamState.eventSource) {
            streamState.eventSource.close();
            streamState.eventSource = null;
        }
        
        streamState.streaming = false;
        streamState.toggle.classList.remove('active');
        streamState.toggle.innerHTML = '<span class="stream-icon">🔴</span> Start Live';
        
        updateLoadingStatus(source, 'Stream paused', false);
        updateStatusIndicator(source, 'offline');
    }

    function addLog(source, log) {
        const streamState = state[source];
        const logId = log.log_id || log.id || `${source}-${Date.now()}-${Math.random()}`;
        
        // Prevent duplicates
        if (streamState.logs.has(logId)) {
            return;
        }
        streamState.logs.add(logId);

        const logElement = createLogElement(log, source);
        streamState.container.prepend(logElement);

        // Limit displayed logs to prevent memory issues
        const maxLogs = 100;
        while (streamState.container.children.length > maxLogs) {
            const removed = streamState.container.removeChild(streamState.container.lastChild);
            const removedId = removed.dataset.logId;
            if (removedId) {
                streamState.logs.delete(removedId);
            }
        }

        // Auto-scroll to top for new logs
        if (streamState.container.scrollTop < 100) {
            streamState.container.scrollTop = 0;
        }
    }

    function createLogElement(log, source) {
        const div = document.createElement('div');
        div.className = 'log-message';
        div.dataset.logId = log.log_id || log.id || `${source}-${Date.now()}`;
        div.dataset.source = source;

        const metadata = log.metadata || {};
        const role = metadata.role || 'system';
        const timestamp = metadata.timestamp || log.created_at || new Date().toISOString();
        const agentId = metadata.agent_id || 'System';
        const text = log.text || '';

        // Add role-based styling
        if (role === 'user') div.classList.add('user-log');
        if (role === 'assistant' || role === 'ollama') div.classList.add('ollama-log');
        if (role === 'system') div.classList.add('system-log');

        // Build GPS info if available
        let gpsInfo = '';
        if (metadata.gps_fix_quality !== undefined || metadata.gps_satellites !== undefined) {
            gpsInfo = '<div class="gps-info">';
            if (metadata.gps_fix_quality !== undefined) {
                gpsInfo += `<span class="gps-metric">Fix Quality: ${metadata.gps_fix_quality}</span>`;
            }
            if (metadata.gps_satellites !== undefined) {
                gpsInfo += `<span class="gps-metric">Satellites: ${metadata.gps_satellites}</span>`;
            }
            if (metadata.gps_signal_quality !== undefined) {
                gpsInfo += `<span class="gps-metric">Signal: ${metadata.gps_signal_quality.toFixed(1)} dB-Hz</span>`;
            }
            gpsInfo += '</div>';
        }

        // Build metadata display
        let metaHtml = '';
        if (metadata.position) {
            metaHtml += `<span class="log-position">📍 ${escapeHtml(String(metadata.position))}</span>`;
        }
        if (metadata.jammed !== undefined) {
            const jammedClass = metadata.jammed ? 'jammed' : 'clear';
            const jammedText = metadata.jammed ? '🚫 Jammed' : '✅ Clear';
            metaHtml += `<span class="log-status ${jammedClass}">${jammedText}</span>`;
        }
        if (metadata.communication_quality !== undefined) {
            const commQuality = (metadata.communication_quality * 100).toFixed(0);
            metaHtml += `<span class="log-quality">📡 Comm: ${commQuality}%</span>`;
        }
        if (log.log_id) {
            const shortId = String(log.log_id).substring(0, 8);
            metaHtml += `<span class="log-id">#${shortId}</span>`;
        }

        div.innerHTML = `
            <div class="log-header">
                <strong>${escapeHtml(String(agentId))}</strong>
                <span class="log-time">${new Date(timestamp).toLocaleString()}</span>
            </div>
            <div class="log-body">${escapeHtml(String(text))}</div>
            ${gpsInfo}
            <div class="log-meta">
                ${metaHtml}
            </div>
        `;

        return div;
    }

    function addChatMessage(message, type = 'bot', status = '') {
        const div = document.createElement('div');
        div.className = `${type}-message`;
        
        if (status) {
            div.classList.add(`message-${status}`);
            const statusIcon = status === 'success' ? '✓' : 
                             status === 'error' ? '✗' : 'ℹ';
            div.innerHTML = `<span class="status-indicator-msg">${statusIcon}</span>${escapeHtml(String(message))}`;
        } else {
            div.textContent = message;
        }

        state.chat.container.appendChild(div);
        state.chat.container.scrollTop = state.chat.container.scrollHeight;
        
        return div;
    }

    async function handleChatSubmit(event) {
        event.preventDefault();
        
        const userInput = state.chat.input.value.trim();
        if (!userInput) return;

        console.log('[CHAT] Sending message:', userInput);

        // Display user message
        addChatMessage(userInput, 'user');
        state.chat.input.value = '';

        // Show loading indicator
        const loadingMsg = addChatMessage('Processing...', 'bot');

        try {
            const response = await fetch('/llm_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userInput })
            });

            const data = await response.json();
            console.log('[CHAT] Received response:', data);
            
            // Remove loading message
            if (loadingMsg.parentNode === state.chat.container) {
                state.chat.container.removeChild(loadingMsg);
            }

            // Determine message status
            let status = 'success';
            const responseText = data.response || 'No response received';
            
            if (responseText.includes('Error') || responseText.includes('Failed')) {
                status = 'error';
            } else if (responseText === 'Not a movement command') {
                status = '';
            }

            // Display response
            const responseMsg = addChatMessage(responseText, 'bot', status);

            // Add live data if available
            if (data.live_data) {
                const liveDataDiv = document.createElement('div');
                liveDataDiv.className = 'live-data-container';
                
                Object.entries(data.live_data).forEach(([agentId, agentData]) => {
                    if (agentData) {
                        const agentDiv = document.createElement('div');
                        agentDiv.className = 'live-agent-data';
                        const x = agentData.x !== undefined ? agentData.x.toFixed(2) : '?';
                        const y = agentData.y !== undefined ? agentData.y.toFixed(2) : '?';
                        const comm = agentData.communication_quality !== undefined ? 
                            (agentData.communication_quality * 100).toFixed(0) : '?';
                        const status = agentData.jammed ? '🚫 Jammed' : '✅ Clear';
                        
                        agentDiv.innerHTML = `
                            <strong>${escapeHtml(agentId)}</strong>:
                            Position (${x}, ${y})
                            | Comm: ${comm}%
                            | ${status}
                        `;
                        liveDataDiv.appendChild(agentDiv);
                    }
                });
                
                responseMsg.appendChild(liveDataDiv);
            }

        } catch (error) {
            console.error('[CHAT] Error:', error);
            
            if (loadingMsg.parentNode === state.chat.container) {
                state.chat.container.removeChild(loadingMsg);
            }
            
            addChatMessage(`Error: ${error.message}`, 'bot', 'error');
        }
    }

    function updateCount(source, count) {
        const countElement = document.getElementById(`${source === 'postgresql' ? 'pg' : 'qdrant'}-count`);
        if (countElement) {
            countElement.textContent = count;
        }
    }

    function updateLoadingStatus(source, message, isError) {
        const loadingElement = document.getElementById(`${source === 'postgresql' ? 'pg' : 'qdrant'}-loading`);
        if (loadingElement) {
            loadingElement.textContent = message;
            loadingElement.classList.toggle('error', isError);
            loadingElement.classList.toggle('active', !isError);
        }
    }

    function updateStatusIndicator(source, status) {
        let indicatorId, textId;
        
        if (source === 'postgresql') {
            indicatorId = 'pg-status';
            textId = 'pg-status-text';
        } else if (source === 'qdrant') {
            indicatorId = 'qdrant-status';
            textId = 'qdrant-status-text';
        } else if (source === 'simulation') {
            indicatorId = 'sim-status';
            textId = 'sim-status-text';
        } else if (source === 'llm') {
            indicatorId = 'llm-status';
            textId = 'llm-status-text';
        }
        
        const indicator = document.getElementById(indicatorId);
        const text = document.getElementById(textId);
        
        if (indicator) {
            indicator.className = `status-indicator ${status}`;
        }
        
        if (text) {
            text.textContent = status === 'online' ? 'Online' : 'Offline';
        }
    }

    async function checkSystemHealth() {
        try {
            const response = await fetch('/health');
            const health = await response.json();
            
            console.log('[HEALTH] Status check:', health);
            
            // Update PostgreSQL status (server is online if we got a response)
            updateStatusIndicator('postgresql', 'online');
            
            // Update Simulation status
            if (health.simulation_api === 'online') {
                updateStatusIndicator('simulation', 'online');
            } else {
                updateStatusIndicator('simulation', 'offline');
            }
            
            // Update Qdrant status
            if (health.qdrant === 'available') {
                updateStatusIndicator('qdrant', 'online');
            } else {
                updateStatusIndicator('qdrant', 'offline');
            }
            
            // Check LLM (Ollama) separately
            try {
                const ollamaResponse = await fetch('http://localhost:11434/api/tags');
                if (ollamaResponse.ok) {
                    updateStatusIndicator('llm', 'online');
                } else {
                    updateStatusIndicator('llm', 'offline');
                }
            } catch (e) {
                updateStatusIndicator('llm', 'offline');
            }
            
        } catch (error) {
            console.error('[HEALTH] Check failed:', error);
            updateStatusIndicator('postgresql', 'offline');
            updateStatusIndicator('qdrant', 'offline');
            updateStatusIndicator('simulation', 'offline');
            updateStatusIndicator('llm', 'offline');
        }
    }

    // Utility function to escape HTML
    function escapeHtml(unsafe) {
        if (unsafe === null || unsafe === undefined) return '';
        return String(unsafe)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    console.log('[INIT] Dashboard script loaded');

})();