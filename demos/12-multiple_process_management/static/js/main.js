/**
 * main.js - Application Initialization
 * Main entry point that coordinates all modules
 */

(function() {
    'use strict';

    /**
     * Initialize the dashboard
     */
    async function initializeDashboard() {
        DashboardUtils.log('INIT', '=== Starting Multi-Agent Simulation Dashboard ===');
        
        try {
            // Step 1: Initialize DOM references
            DashboardUtils.log('INIT', 'Step 1: Initializing DOM references...');
            const domReady = DashboardState.initializeDOMReferences();
            
            if (!domReady) {
                DashboardUtils.error('INIT', 'Failed to initialize DOM references. Cannot continue.');
                showErrorMessage('Failed to initialize dashboard. Please check console for details.');
                return;
            }
            
            // Step 2: Setup event listeners
            DashboardUtils.log('INIT', 'Step 2: Setting up event listeners...');
            StreamManager.setupEventListeners();
            ChatManager.setupEventListeners();
            
            // Step 3: Start health monitoring
            DashboardUtils.log('INIT', 'Step 3: Starting health monitoring...');
            HealthMonitor.startMonitoring(10000); // Check every 10 seconds
            
            // Step 4: Initialize streaming
            DashboardUtils.log('INIT', 'Step 4: Initializing streaming...');
            await StreamManager.initialize();
            
            DashboardUtils.log('INIT', '=== Dashboard initialization complete ===');
            
        } catch (error) {
            DashboardUtils.error('INIT', 'Fatal error during initialization', error);
            showErrorMessage(`Initialization failed: ${error.message}`);
        }
    }

    /**
     * Show error message to user
     */
    function showErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #f44336;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            z-index: 10000;
            max-width: 400px;
        `;
        errorDiv.innerHTML = `
            <strong>Error</strong><br>
            ${DashboardUtils.escapeHtml(message)}
        `;
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                document.body.removeChild(errorDiv);
            }
        }, 10000);
    }

    /**
     * Check if all required modules are loaded
     */
    function checkModules() {
        const requiredModules = [
            'DashboardUtils',
            'DashboardState',
            'HealthMonitor',
            'LogManager',
            'StreamManager',
            'ChatManager'
        ];
        
        const missingModules = requiredModules.filter(module => !window[module]);
        
        if (missingModules.length > 0) {
            console.error('[INIT] Missing required modules:', missingModules);
            showErrorMessage(`Missing modules: ${missingModules.join(', ')}`);
            return false;
        }
        
        return true;
    }

    /**
     * DOM Content Loaded event handler
     */
    document.addEventListener('DOMContentLoaded', function() {
        DashboardUtils.log('INIT', 'DOM Content Loaded');
        
        // Check if all modules are loaded
        if (!checkModules()) {
            DashboardUtils.error('INIT', 'Not all modules loaded. Cannot start.');
            return;
        }
        
        // Initialize the dashboard
        initializeDashboard();
    });

    /**
     * Window load event handler (backup)
     */
    window.addEventListener('load', function() {
        // If dashboard wasn't initialized on DOMContentLoaded, try again
        if (!DashboardState.postgresql.container) {
            DashboardUtils.log('INIT', 'Retrying initialization on window load...');
            if (checkModules()) {
                initializeDashboard();
            }
        }
    });

    /**
     * Handle page visibility changes
     */
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            DashboardUtils.log('INIT', 'Page hidden - pausing non-essential operations');
        } else {
            DashboardUtils.log('INIT', 'Page visible - resuming operations');
            // Trigger a health check when page becomes visible
            HealthMonitor.checkSystemHealth();
        }
    });

    /**
     * Handle errors globally
     */
    window.addEventListener('error', function(event) {
        DashboardUtils.error('GLOBAL', 'Uncaught error', {
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno,
            error: event.error
        });
    });

    /**
     * Handle unhandled promise rejections
     */
    window.addEventListener('unhandledrejection', function(event) {
        DashboardUtils.error('GLOBAL', 'Unhandled promise rejection', {
            reason: event.reason,
            promise: event.promise
        });
    });

    DashboardUtils.log('INIT', 'Main script loaded and ready');

})();