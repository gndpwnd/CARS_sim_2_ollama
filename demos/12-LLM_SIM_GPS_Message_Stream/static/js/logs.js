/**
 * logs.js - Log Display Management (FIXED - handles null GPS values)
 * Handles creation and display of log messages
 */

const LogManager = {
    /**
     * Create a log element
     */
    createLogElement: function(log, source) {
        const div = document.createElement('div');
        div.className = 'log-message';
        div.dataset.logId = log.log_id || log.id || DashboardUtils.generateId(source);
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

        // Build GPS info if available - WITH NULL CHECKS
        let gpsInfo = '';
        if (metadata.gps_fix_quality !== undefined || metadata.gps_satellites !== undefined) {
            gpsInfo = '<div class="gps-info">';
            if (metadata.gps_fix_quality !== undefined && metadata.gps_fix_quality !== null) {
                gpsInfo += `<span class="gps-metric">Fix Quality: ${metadata.gps_fix_quality}</span>`;
            }
            if (metadata.gps_satellites !== undefined && metadata.gps_satellites !== null) {
                gpsInfo += `<span class="gps-metric">Satellites: ${metadata.gps_satellites}</span>`;
            }
            if (metadata.gps_signal_quality !== undefined && metadata.gps_signal_quality !== null) {
                gpsInfo += `<span class="gps-metric">Signal: ${metadata.gps_signal_quality.toFixed(1)} dB-Hz</span>`;
            }
            gpsInfo += '</div>';
        }

        // Build metadata display
        let metaHtml = '';
        if (metadata.position) {
            metaHtml += `<span class="log-position">📍 ${DashboardUtils.escapeHtml(String(metadata.position))}</span>`;
        }
        if (metadata.jammed !== undefined) {
            const jammedClass = metadata.jammed ? 'jammed' : 'clear';
            const jammedText = metadata.jammed ? '🚫 Jammed' : '✅ Clear';
            metaHtml += `<span class="log-status ${jammedClass}">${jammedText}</span>`;
        }
        if (metadata.communication_quality !== undefined && metadata.communication_quality !== null) {
            const commQuality = (metadata.communication_quality * 100).toFixed(0);
            metaHtml += `<span class="log-quality">📡 Comm: ${commQuality}%</span>`;
        }
        if (log.log_id) {
            const shortId = String(log.log_id).substring(0, 8);
            metaHtml += `<span class="log-id">#${shortId}</span>`;
        }

        div.innerHTML = `
            <div class="log-header">
                <strong>${DashboardUtils.escapeHtml(String(agentId))}</strong>
                <span class="log-time">${DashboardUtils.formatTimestamp(timestamp)}</span>
            </div>
            <div class="log-body">${DashboardUtils.escapeHtml(String(text))}</div>
            ${gpsInfo}
            <div class="log-meta">
                ${metaHtml}
            </div>
        `;

        return div;
    },

    /**
     * Add log to container
     */
    addLog: function(source, log) {
        const streamState = DashboardState.getStreamState(source);
        const logId = log.log_id || log.id || DashboardUtils.generateId(source);
        
        // Prevent duplicates
        if (streamState.logs.has(logId)) {
            return;
        }
        streamState.logs.add(logId);

        const logElement = this.createLogElement(log, source);
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

        // Update count
        DashboardState.updateCount(source, streamState.logs.size);

        // Auto-scroll to top for new logs
        if (streamState.container.scrollTop < 100) {
            streamState.container.scrollTop = 0;
        }
    },

    /**
     * Load initial data for a source
     */
    loadInitialData: async function(source) {
        DashboardUtils.log('LOGS', `Loading initial data for ${source}...`);
        
        try {
            const response = await fetch(`/data/${source}`);
            const data = await response.json();
            
            if (data.logs && data.logs.length > 0) {
                DashboardUtils.log('LOGS', `Loaded ${data.logs.length} ${source} logs`);
                
                const streamState = DashboardState.getStreamState(source);
                
                // Clear empty state
                streamState.container.innerHTML = '';
                
                // Add logs in reverse order (newest first)
                data.logs.reverse().forEach(log => this.addLog(source, log));
            }
        } catch (error) {
            DashboardUtils.error('LOGS', `Failed to load ${source} data`, error);
            this.updateLoadingStatus(source, 'Failed to load initial data', true);
        }
    },

    /**
     * Update loading status
     */
    updateLoadingStatus: function(source, message, isError) {
        const loadingElement = document.getElementById(`${source === 'postgresql' ? 'pg' : 'qdrant'}-loading`);
        if (loadingElement) {
            loadingElement.textContent = message;
            loadingElement.classList.toggle('error', isError);
            loadingElement.classList.toggle('active', !isError);
        }
    }
};

// Make log manager available globally
window.LogManager = LogManager;