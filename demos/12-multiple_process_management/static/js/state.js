/**
 * state.js - Application State Management
 * Centralized state for the dashboard
 */

const DashboardState = {
    // PostgreSQL stream state
    postgresql: {
        logs: new Set(),
        streaming: false,
        eventSource: null,
        container: null,
        toggle: null,
        count: 0
    },
    
    // Qdrant stream state
    qdrant: {
        logs: new Set(),
        streaming: false,
        eventSource: null,
        container: null,
        toggle: null,
        count: 0
    },
    
    // Chat state
    chat: {
        container: null,
        form: null,
        input: null
    },
    
    // System health state
    health: {
        postgresql: 'offline',
        qdrant: 'offline',
        simulation: 'offline',
        llm: 'offline'
    },
    
    /**
     * Initialize DOM references
     */
    initializeDOMReferences: function() {
        DashboardUtils.log('STATE', 'Initializing DOM references...');
        
        // PostgreSQL elements
        this.postgresql.container = document.getElementById('postgresql-container');
        this.postgresql.toggle = document.getElementById('pg-stream-toggle');
        
        // Qdrant elements
        this.qdrant.container = document.getElementById('qdrant-container');
        this.qdrant.toggle = document.getElementById('qdrant-stream-toggle');
        
        // Chat elements
        this.chat.container = document.getElementById('chat-container');
        this.chat.form = document.getElementById('message-form');
        this.chat.input = document.getElementById('message-input');
        
        // Verify all elements exist
        const missingElements = [];
        
        if (!this.postgresql.container) missingElements.push('postgresql-container');
        if (!this.postgresql.toggle) missingElements.push('pg-stream-toggle');
        if (!this.qdrant.container) missingElements.push('qdrant-container');
        if (!this.qdrant.toggle) missingElements.push('qdrant-stream-toggle');
        if (!this.chat.container) missingElements.push('chat-container');
        if (!this.chat.form) missingElements.push('message-form');
        if (!this.chat.input) missingElements.push('message-input');
        
        if (missingElements.length > 0) {
            DashboardUtils.error('STATE', 'Missing DOM elements:', missingElements);
            return false;
        }
        
        DashboardUtils.log('STATE', 'All DOM references initialized successfully');
        return true;
    },
    
    /**
     * Update count for a source
     */
    updateCount: function(source, count) {
        this[source].count = count;
        const countElement = document.getElementById(`${source === 'postgresql' ? 'pg' : 'qdrant'}-count`);
        if (countElement) {
            countElement.textContent = count;
        }
    },
    
    /**
     * Get stream state
     */
    getStreamState: function(source) {
        return this[source];
    },
    
    /**
     * Reset state for a source
     */
    resetSource: function(source) {
        this[source].logs.clear();
        this[source].streaming = false;
        this[source].count = 0;
        if (this[source].eventSource) {
            this[source].eventSource.close();
            this[source].eventSource = null;
        }
    }
};

// Make state available globally
window.DashboardState = DashboardState;