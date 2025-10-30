/**
 * utils.js - Utility Functions
 * Common helper functions used across the application
 */

const DashboardUtils = {
    /**
     * Escape HTML to prevent XSS attacks
     */
    escapeHtml: function(unsafe) {
        if (unsafe === null || unsafe === undefined) return '';
        return String(unsafe)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    /**
     * Format timestamp to locale string
     */
    formatTimestamp: function(timestamp) {
        try {
            return new Date(timestamp).toLocaleString();
        } catch (e) {
            return timestamp;
        }
    },

    /**
     * Generate unique ID
     */
    generateId: function(prefix = 'id') {
        return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    },

    /**
     * Debounce function
     */
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Throttle function
     */
    throttle: function(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * Log with timestamp
     */
    log: function(category, message, data = null) {
        const timestamp = new Date().toISOString();
        const logMessage = `[${timestamp}] [${category}] ${message}`;
        
        if (data) {
            console.log(logMessage, data);
        } else {
            console.log(logMessage);
        }
    },

    /**
     * Error logging
     */
    error: function(category, message, error = null) {
        const timestamp = new Date().toISOString();
        const errorMessage = `[${timestamp}] [${category}] ERROR: ${message}`;
        
        if (error) {
            console.error(errorMessage, error);
        } else {
            console.error(errorMessage);
        }
    }
};

// Make utilities available globally
window.DashboardUtils = DashboardUtils;