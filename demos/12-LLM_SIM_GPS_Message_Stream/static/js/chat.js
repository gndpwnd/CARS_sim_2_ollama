/**
 * chat.js - Chat Interface Management
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
            div.textContent = message;
        }

        DashboardState.chat.container.appendChild(div);
        DashboardState.chat.container.scrollTop = DashboardState.chat.container.scrollHeight;
        
        return div;
    },

    /**
     * Handle chat form submission
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
            const response = await fetch('/llm_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userInput })
            });

            const data = await response.json();
            DashboardUtils.log('CHAT', 'Received response:', data);
            
            // Remove loading message
            if (loadingMsg.parentNode === DashboardState.chat.container) {
                DashboardState.chat.container.removeChild(loadingMsg);
            }

            // Determine message status
            let status = 'success';
            const responseText = data.response || 'No response received';
            
            if (responseText.includes('Error') || responseText.includes('Failed')) {
                status = 'error';
            }

            // Display response
            const responseMsg = this.addChatMessage(responseText, 'bot', status);

            // Add live data if available
            if (data.live_data) {
                this.addLiveDataDisplay(responseMsg, data.live_data);
            }

        } catch (error) {
            DashboardUtils.error('CHAT', 'Error sending message', error);
            
            if (loadingMsg.parentNode === DashboardState.chat.container) {
                DashboardState.chat.container.removeChild(loadingMsg);
            }
            
            this.addChatMessage(`Error: ${error.message}`, 'bot', 'error');
        }
    },

    /**
     * Add live data display to a message
     */
    addLiveDataDisplay: function(messageElement, liveData) {
        const liveDataDiv = document.createElement('div');
        liveDataDiv.className = 'live-data-container';
        
        Object.entries(liveData).forEach(([agentId, agentData]) => {
            if (agentData) {
                const agentDiv = document.createElement('div');
                agentDiv.className = 'live-agent-data';
                
                const x = agentData.x !== undefined ? agentData.x.toFixed(2) : '?';
                const y = agentData.y !== undefined ? agentData.y.toFixed(2) : '?';
                const comm = agentData.communication_quality !== undefined ? 
                    (agentData.communication_quality * 100).toFixed(0) : '?';
                
                agentDiv.textContent = `${agentId}: (${x}, ${y}) - Comm: ${comm}%`;
                liveDataDiv.appendChild(agentDiv);
            }
        });
        
        messageElement.appendChild(liveDataDiv);
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
     * Display formatted message
     */
    displayMessage: function(role, content) {
        const chatContainer = document.getElementById('chat-container');
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        // Simple markdown-like formatting
        let formattedContent = content
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')  // Bold
            .replace(/`(.+?)`/g, '<code>$1</code>')  // Inline code
            .replace(/^- (.+)$/gm, '<li>$1</li>')  // List items
            .replace(/\n/g, '<br>');  // Line breaks
        
        // Wrap list items
        formattedContent = formattedContent.replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>');
        
        messageDiv.innerHTML = `
            <div class="message-header">${role === 'user' ? '👤 You' : '🤖 Assistant'}</div>
            <div class="message-content">${formattedContent}</div>
        `;
        
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    },

    /**
     * Load startup menu
     */
    loadStartupMenu: async function() {
        try {
            const response = await fetch('/startup_menu');
            const data = await response.json();
            
            if (data.menu) {
                this.displayMessage('bot', data.menu);
            }
            
        } catch (error) {
            console.error('Failed to load startup menu:', error);
            this.displayMessage('system', '⚠️ Welcome! Type "help" for available commands.');
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

        // Load startup menu when DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            this.loadStartupMenu();
        });
    }
};

// Export ChatManager for use in other modules
window.ChatManager = ChatManager;