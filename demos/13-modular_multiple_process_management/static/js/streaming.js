/**
 * streaming.js - Real-time Stream Management (FIXED with debug logging)
 */

const StreamManager = {
    /**
     * Start streaming for a source
     */
    startStream: function(source) {
        const streamState = DashboardState.getStreamState(source);
        const endpoint = `/stream/${source}`;

        DashboardUtils.log('STREAM', `Starting ${source} stream from ${endpoint}...`);
        
        // Close existing connection if any
        if (streamState.eventSource) {
            streamState.eventSource.close();
        }
        
        streamState.eventSource = new EventSource(endpoint);
        streamState.streaming = true;
        
        // Update button UI
        this.updateStreamButton(source, true);

        // Handle incoming messages
        streamState.eventSource.onmessage = (event) => {
            try {
                // DEBUG: Log raw data received
                if (Math.random() < 0.1) { // Log 10% of messages to avoid spam
                    DashboardUtils.log('STREAM', `${source} received data:`, event.data.substring(0, 100));
                }
                
                const log = JSON.parse(event.data);
                
                // Validate log data
                if (!log || (log.error && !log.log_id)) {
                    // Skip error messages that aren't actual logs
                    return;
                }
                
                LogManager.addLog(source, log);
            } catch (error) {
                DashboardUtils.error('STREAM', `Error parsing ${source} stream data`, error);
                console.log('Raw data that failed to parse:', event.data);
            }
        };

        // Handle errors with smart reconnection
        streamState.eventSource.onerror = (error) => {
            DashboardUtils.error('STREAM', `${source} stream error`, error);
            
            // Check if connection is still open
            if (streamState.eventSource.readyState === EventSource.CONNECTING) {
                LogManager.updateLoadingStatus(source, '🔄 Reconnecting...', false);
            } else if (streamState.eventSource.readyState === EventSource.CLOSED) {
                LogManager.updateLoadingStatus(source, '⚠️ Stream disconnected, retrying...', true);
                
                // Close and reconnect
                streamState.eventSource.close();
                
                // Auto-reconnect after 3 seconds if still supposed to be streaming
                setTimeout(() => {
                    if (streamState.streaming) {
                        DashboardUtils.log('STREAM', `Attempting to reconnect ${source}...`);
                        this.startStream(source);
                    }
                }, 3000);
            }
        };

        // Handle open
        streamState.eventSource.onopen = () => {
            DashboardUtils.log('STREAM', `${source} stream connected ✓`);
            LogManager.updateLoadingStatus(source, '🟢 Live streaming', false);
            HealthMonitor.updateStatusIndicator(source, 'online');
        };
    },

    /**
     * Stop streaming for a source
     */
    stopStream: function(source) {
        const streamState = DashboardState.getStreamState(source);
        
        DashboardUtils.log('STREAM', `Stopping ${source} stream...`);
        
        if (streamState.eventSource) {
            streamState.eventSource.close();
            streamState.eventSource = null;
        }
        
        streamState.streaming = false;
        
        // Update button UI
        this.updateStreamButton(source, false);
        
        LogManager.updateLoadingStatus(source, 'Stream paused', false);
        HealthMonitor.updateStatusIndicator(source, 'offline');
    },

    /**
     * Toggle streaming for a source
     */
    toggleStream: function(source) {
        const streamState = DashboardState.getStreamState(source);
        
        if (streamState.streaming) {
            this.stopStream(source);
        } else {
            this.startStream(source);
        }
    },

    /**
     * Update stream button UI
     */
    updateStreamButton: function(source, isActive) {
        const streamState = DashboardState.getStreamState(source);
        
        if (isActive) {
            streamState.toggle.classList.add('active');
            streamState.toggle.innerHTML = '<span class="stream-icon">🟢</span> Live';
        } else {
            streamState.toggle.classList.remove('active');
            streamState.toggle.innerHTML = '<span class="stream-icon">🔴</span> Start Live';
        }
    },

    /**
     * Setup event listeners for stream toggles
     */
    setupEventListeners: function() {
        DashboardUtils.log('STREAM', 'Setting up stream event listeners...');
        
        // PostgreSQL stream toggle
        DashboardState.postgresql.toggle.addEventListener('click', () => {
            this.toggleStream('postgresql');
        });

        // Qdrant stream toggle
        DashboardState.qdrant.toggle.addEventListener('click', () => {
            this.toggleStream('qdrant');
        });
    },

    /**
     * Initialize streaming with ALL data
     */
    initialize: async function() {
        DashboardUtils.log('STREAM', 'Initializing streaming...');
        
        // Load ALL initial data (not just 50)
        DashboardUtils.log('STREAM', 'Loading initial PostgreSQL data...');
        await LogManager.loadInitialData('postgresql');
        
        DashboardUtils.log('STREAM', 'Loading initial Qdrant data...');
        await LogManager.loadInitialData('qdrant');
        
        // Auto-start streaming after initial load
        setTimeout(() => {
            DashboardUtils.log('STREAM', 'Auto-starting live streams...');
            this.startStream('postgresql');
            this.startStream('qdrant');
        }, 1000);
    }
};

// Make stream manager available globally
window.StreamManager = StreamManager;