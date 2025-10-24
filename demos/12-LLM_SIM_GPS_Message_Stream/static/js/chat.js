/**
 * chat.js - Chat Interface Management (FIXED)
 * Handles chat messages and LLM interactions
 */

const ChatManager = {
    /**
     * Add a chat message to the container
     */
    addChatMessage: function(message, type = 'bot', status = '') {
        const div = document.createElement('div');
        div.className = `${type}-message`;
        
        if (status) {
            div.classList.add(`message-${status}`);
            const statusIcon = status === 'success' ? '✓' : 
                             status === 'error' ? '✗' : 'ℹ';
            div.innerHTML = `<span class="status-indicator-msg">${statusIcon}</span>${DashboardUtils.escapeHtml(String(message))}`;
        } else {
            // Support markdown-like formatting
            const formatted = this.formatMessage(message);
            div.innerHTML = formatted;
        }

        DashboardState.chat.container.appendChild(div);
        DashboardState.chat.container.scrollTop = DashboardState.chat.container.scrollHeight;
        
        return div;
    },

    /**
     * Format message with markdown-like syntax
     */
    formatMessage: function(text) {
        let formatted = DashboardUtils.escapeHtml(String(text));
        
        // Bold: **text**
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Inline code: `text`
        formatted = formatted.replace(/`(.+?)`/g, '<code>$1</code>');
        
        // Bullet points: - text
        formatted = formatted.replace(/^- (.+)$/gm, '<li>$1</li>');
        
        // Wrap lists
        formatted = formatted.replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>');
        
        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    },

    /**
     * Handle chat form submission (FIXED)
     */
    handleChatSubmit: async function(event) {
        event.preventDefault();
        
        const userInput = DashboardState.chat.input.value.trim();
        if (!userInput) return;

        DashboardUtils.log('CHAT', 'Sending message:', userInput);

        // Display user message
        this.addChatMessage(userInput, 'user');
        DashboardState.chat.input.value = '';

        // Show loading indicator
        const loadingMsg = this.addChatMessage('Processing...', 'bot');

        try {
            // FIXED: Use /chat endpoint instead of /llm_command
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userInput })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            DashboardUtils.log('CHAT', 'Received response:', data);
            
            // Remove loading message
            if (loadingMsg.parentNode === DashboardState.chat.container) {
                DashboardState.chat.container.removeChild(loadingMsg);
            }

            // Determine message status
            let status = '';
            const responseText = data.response || 'No response received';
            
            if (data.error || responseText.toLowerCase().includes('error')) {
                status = 'error';
            }

            // Display response
            this.addChatMessage(responseText, 'bot', status);

        } catch (error) {
            DashboardUtils.error('CHAT', 'Error sending message', error);
            
            if (loadingMsg.parentNode === DashboardState.chat.container) {
                DashboardState.chat.container.removeChild(loadingMsg);
            }
            
            this.addChatMessage(`Error: ${error.message}`, 'bot', 'error');
        }
    },

    /**
     * Clear chat messages
     */
    clearChat: function() {
        const welcomeMsg = DashboardState.chat.container.querySelector('.welcome-message');
        DashboardState.chat.container.innerHTML = '';
        
        if (welcomeMsg) {
            DashboardState.chat.container.appendChild(welcomeMsg);
        }
        
        this.addChatMessage('Chat cleared', 'bot');
    },

    /**
     * Load startup menu (FIXED)
     */
    loadStartupMenu: async function() {
        try {
            DashboardUtils.log('CHAT', 'Loading startup menu...');
            
            const response = await fetch('/startup_menu');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.menu) {
                // Remove welcome message if present
                const welcomeMsg = DashboardState.chat.container.querySelector('.welcome-message');
                if (welcomeMsg) {
                    DashboardState.chat.container.removeChild(welcomeMsg);
                }
                
                this.addChatMessage(data.menu, 'bot');
                DashboardUtils.log('CHAT', 'Startup menu loaded successfully');
            } else {
                throw new Error('No menu in response');
            }
            
        } catch (error) {
            DashboardUtils.error('CHAT', 'Failed to load startup menu', error);
            this.addChatMessage('⚠️ Welcome! Type "help" for available commands.', 'bot');
        }
    },

    /**
     * Setup event listeners
     */
    setupEventListeners: function() {
        DashboardUtils.log('CHAT', 'Setting up chat event listeners...');
        
        // Chat form submission
        DashboardState.chat.form.addEventListener('submit', (e) => {
            this.handleChatSubmit(e);
        });

        // Clear chat button
        const clearChatBtn = document.getElementById('clear-chat');
        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', () => this.clearChat());
        }

        // Load startup menu after short delay
        setTimeout(() => {
            this.loadStartupMenu();
        }, 500);
    }
};

// Export ChatManager for use in other modules
window.ChatManager = ChatManager;