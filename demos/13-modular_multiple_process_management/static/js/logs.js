/**
 * logs.js - Log Display Management
 * Shows latest 200 messages per stream
 */

const LogManager = {
    MAX_LOGS: 200,  // Show latest 200 messages

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

        // Build GPS info if available
        let gpsInfo = '';
        if (metadata.gps_fix_quality !== undefined || metadata.gps_satellites !== undefined) {
            gpsInfo = '<div class="gps-info">';
            if (metadata.gps_fix_quality !== undefined && metadata.gps_fix_quality !== null) {
                gpsInfo += `<span class="gps-metric">Fix: ${metadata.gps_fix_quality}</span>`;
            }
            if (metadata.gps_satellites !== undefined && metadata.gps_satellites !== null) {
                gpsInfo += `<span class="gps-metric">Sats: ${metadata.gps_satellites}</span>`;
            }
            if (metadata.gps_signal_quality !== undefined && metadata.gps_signal_quality !== null) {
                gpsInfo += `<span class="gps-metric">Signal: ${metadata.gps_signal_quality.toFixed(1)} dB</span>`;
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
            metaHtml += `<span class="log-quality">📡 ${commQuality}%</span>`;
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
            <div class="log-meta">${metaHtml}</div>
        `;

        return div;
    },

    /**
     * Add log to container (newest at top)
     */
    addLog: function(source, log) {
        const streamState = DashboardState.getStreamState(source);
        const logId = log.log_id || log.id || DashboardUtils.generateId(source);
        
        // Skip duplicates
        if (streamState.logs.has(logId)) return;
        streamState.logs.add(logId);

        // Add to top
        const logElement = this.createLogElement(log, source);
        streamState.container.prepend(logElement);

        // Keep only latest MAX_LOGS messages
        while (streamState.container.children.length > this.MAX_LOGS) {
            const removed = streamState.container.removeChild(streamState.container.lastChild);
            const removedId = removed.dataset.logId;
            if (removedId) streamState.logs.delete(removedId);
        }

        // Update count
        DashboardState.updateCount(source, streamState.logs.size);

        // Update badge if at limit
        const countBadge = document.getElementById(source === 'postgresql' ? 'pg-count' : 'qdrant-count');
        if (countBadge) {
            countBadge.classList.toggle('at-limit', streamState.logs.size >= this.MAX_LOGS);
            countBadge.title = streamState.logs.size >= this.MAX_LOGS 
                ? `Showing ${this.MAX_LOGS} most recent` 
                : '';
        }

        // Auto-scroll to top if near top
        if (streamState.container.scrollTop < 100) {
            streamState.container.scrollTop = 0;
        }
    },

    /**
     * Load initial data
     */
    loadInitialData: async function(source) {
        DashboardUtils.log('LOGS', `Loading ${source} logs...`);
        
        try {
            const response = await fetch(`/data/${source}`);
            const data = await response.json();
            
            if (data.logs && data.logs.length > 0) {
                const streamState = DashboardState.getStreamState(source);
                streamState.container.innerHTML = '';
                
                // Take only latest MAX_LOGS
                const logsToShow = data.logs.slice(0, this.MAX_LOGS);
                logsToShow.forEach(log => this.addLog(source, log));
                
                DashboardUtils.log('LOGS', `✓ Loaded ${logsToShow.length} ${source} logs`);
            } else {
                DashboardUtils.log('LOGS', `No ${source} logs yet`);
                this.updateLoadingStatus(source, 'No data yet', false);
            }
        } catch (error) {
            DashboardUtils.error('LOGS', `Failed to load ${source}`, error);
            this.updateLoadingStatus(source, 'Failed to load', true);
        }
    },

    /**
     * Update loading status
     */
    updateLoadingStatus: function(source, message, isError) {
        const loadingElement = document.getElementById(
            source === 'postgresql' ? 'pg-loading' : 'qdrant-loading'
        );
        if (loadingElement) {
            loadingElement.textContent = message;
            loadingElement.classList.toggle('error', isError);
            loadingElement.classList.toggle('active', !isError);
        }
    }
};

window.LogManager = LogManager;