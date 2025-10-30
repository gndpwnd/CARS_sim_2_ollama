/**
 * streaming.js - Real-time Stream Management
 * Handles EventSource connections for live data streaming
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
                const log = JSON.parse(event.data);
                LogManager.addLog(source, log);
            } catch (error) {
                DashboardUtils.error('STREAM', `Error parsing ${source} stream data`, error);
            }
        };

        // Handle errors
        streamState.eventSource.onerror = (error) => {
            DashboardUtils.error('STREAM', `${source} stream error`, error);
            LogManager.updateLoadingStatus(source, '⚠️ Stream disconnected, retrying...', true);
            
            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                if (streamState.streaming) {
                    DashboardUtils.log('STREAM', `Attempting to reconnect ${source}...`);
                    this.stopStream(source);
                    setTimeout(() => this.startStream(source), 1000);
                }
            }, 3000);
        };

        // Handle open
        streamState.eventSource.onopen = () => {
            DashboardUtils.log('STREAM', `${source} stream connected`);
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
     * Initialize streaming
     */
    initialize: async function() {
        DashboardUtils.log('STREAM', 'Initializing streaming...');
        
        // Load initial data
        await LogManager.loadInitialData('postgresql');
        await LogManager.loadInitialData('qdrant');
        
        // Auto-start streaming after a delay
        setTimeout(() => {
            DashboardUtils.log('STREAM', 'Auto-starting streams...');
            this.startStream('postgresql');
            this.startStream('qdrant');
        }, 1000);
    }
};

// Make stream manager available globally
window.StreamManager = StreamManager;