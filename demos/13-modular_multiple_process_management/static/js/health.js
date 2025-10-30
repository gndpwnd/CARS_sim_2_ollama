/**
 * health.js - System Health Monitoring
 * Monitors and displays health status of all system components
 */

const HealthMonitor = {
    /**
     * Update status indicator in UI
     */
    updateStatusIndicator: function(source, status) {
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
        
        // Update state
        DashboardState.health[source] = status;
    },
    
    /**
     * Check system health
     */
    checkSystemHealth: async function() {
        try {
            const response = await fetch('/health');
            const health = await response.json();
            
            DashboardUtils.log('HEALTH', 'Health check response:', health);
            
            // Update PostgreSQL status (if we got a response, server is online)
            this.updateStatusIndicator('postgresql', 'online');
            
            // Update Simulation status
            if (health.simulation_api === 'online') {
                this.updateStatusIndicator('simulation', 'online');
            } else {
                this.updateStatusIndicator('simulation', 'offline');
            }
            
            // Update Qdrant status
            if (health.qdrant === 'available') {
                this.updateStatusIndicator('qdrant', 'online');
            } else {
                this.updateStatusIndicator('qdrant', 'offline');
            }
            
            // Check LLM (Ollama) separately
            this.checkOllamaHealth();
            
        } catch (error) {
            DashboardUtils.error('HEALTH', 'Health check failed', error);
            this.updateStatusIndicator('postgresql', 'offline');
            this.updateStatusIndicator('qdrant', 'offline');
            this.updateStatusIndicator('simulation', 'offline');
            this.updateStatusIndicator('llm', 'offline');
        }
    },
    
    /**
     * Check Ollama health
     */
    checkOllamaHealth: async function() {
        try {
            const ollamaResponse = await fetch('http://localhost:11434/api/tags', {
                method: 'GET',
                mode: 'cors'
            });
            
            if (ollamaResponse.ok) {
                this.updateStatusIndicator('llm', 'online');
            } else {
                this.updateStatusIndicator('llm', 'offline');
            }
        } catch (e) {
            DashboardUtils.error('HEALTH', 'Ollama check failed', e);
            this.updateStatusIndicator('llm', 'offline');
        }
    },
    
    /**
     * Start periodic health checks
     */
    startMonitoring: function(interval = 10000) {
        DashboardUtils.log('HEALTH', `Starting health monitoring (interval: ${interval}ms)`);
        
        // Initial check
        this.checkSystemHealth();
        
        // Periodic checks
        setInterval(() => {
            this.checkSystemHealth();
        }, interval);
    }
};

// Make health monitor available globally
window.HealthMonitor = HealthMonitor;