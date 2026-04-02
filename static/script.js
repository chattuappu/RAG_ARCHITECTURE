document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const sampleBtns = document.querySelectorAll('.sample-btn');
    const sidebar = document.querySelector('.sidebar');
    const appContainer = document.querySelector('.app-container');
    const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');

    // Configure marked to use breaks for better text wrapping, and sanitize if needed
    marked.use({
        breaks: true,
        gfm: true
    });

    // Chat history
    let isWaitingForResponse = false;

    // Scroll to bottom
    const scrollToBottom = () => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    };

    // Add a message to the UI
    const addMessage = (role, content, sources = null, timestamp = null) => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = `avatar ${role}`;
        avatarDiv.innerText = role === 'user' ? 'U' : '💬';
        
        // Content container
        const contentContainer = document.createElement('div');
        contentContainer.className = 'message-content';

        // Markdown content
        const markdownDiv = document.createElement('div');
        if (role === 'user') {
            // For user inputs, just show as text to avoid markdown injection
            markdownDiv.textContent = content; 
            contentContainer.appendChild(markdownDiv);
        } else {
            // Parse Markdown for assistant
            markdownDiv.innerHTML = marked.parse(content);
            contentContainer.appendChild(markdownDiv);
        }

        // Sources and Timestamp
        if (role === 'assistant') {
            if (sources) {
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'sources-container';
                const sourcesTitle = document.createElement('div');
                sourcesTitle.className = 'sources-title';
                sourcesTitle.innerText = 'Sources:';
                sourcesDiv.appendChild(sourcesTitle);

                const ul = document.createElement('ul');
                ul.className = 'sources-list';
                if (sources.length > 0) {
                    sources.forEach(src => {
                        const li = document.createElement('li');
                        li.innerText = src;
                        ul.appendChild(li);
                    });
                } else {
                    const info = document.createElement('p');
                    info.style.margin = "0";
                    info.innerText = "No specific context found.";
                    ul.appendChild(info);
                }
                sourcesDiv.appendChild(ul);
                contentContainer.appendChild(sourcesDiv);
            }

            if (timestamp) {
                const timeDiv = document.createElement('div');
                timeDiv.className = 'timestamp';
                timeDiv.innerText = `Generated at: ${timestamp}`;
                contentContainer.appendChild(timeDiv);
            }
        }

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentContainer);
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    };

    const addTypingIndicator = () => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message assistant typing`;
        messageDiv.id = 'typing-indicator-wrapper';
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = `avatar assistant`;
        avatarDiv.innerText = '💬';
        
        const contentContainer = document.createElement('div');
        contentContainer.className = 'message-content';
        
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        
        contentContainer.appendChild(indicator);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentContainer);
        
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
    };

    const removeTypingIndicator = () => {
        const el = document.getElementById('typing-indicator-wrapper');
        if (el) el.remove();
    };

    const handleSend = async (queryText) => {
        if (!queryText.trim() || isWaitingForResponse) return;
        
        // Reset input immediately
        chatInput.value = '';
        chatInput.style.height = '';
        
        // Disable inputs and show send-button loading state
        isWaitingForResponse = true;
        sendBtn.disabled = true;
        sendBtn.classList.add('loading');
        chatInput.disabled = true;

        // Add user message and initial assistant skeleton
        addMessage('user', queryText);
        addTypingIndicator();

        let assistantMessageDiv = null;
        let assistantContentDiv = null;
        let assembledAnswer = '';
        
        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: queryText })
            });

            if (!response.ok) {
                // Get error details from response body for logging
                let errorDetail = `Server returned ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || errorData.message || errorDetail;
                    console.error('API Error:', errorData);
                } catch (e) {
                    console.error('API Error:', errorDetail);
                }
                throw new Error(errorDetail);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let hasDoneEvent = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim()) continue;
                    let payload;
                    try {
                        payload = JSON.parse(line);
                    } catch (parseError) {
                        console.warn('Stream parse error', parseError, line);
                        continue;
                    }

                    if (payload.type === 'token') {
                        // Create assistant message div on first token
                        if (!assistantMessageDiv) {
                            removeTypingIndicator();
                            assistantMessageDiv = addMessage('assistant', '');
                            assistantContentDiv = assistantMessageDiv.querySelector('.message-content > div');
                        }
                        
                        assembledAnswer += payload.text;
                        assistantContentDiv.innerHTML = marked.parse(assembledAnswer);
                        scrollToBottom();
                    } else if (payload.type === 'done') {
                        hasDoneEvent = true;

                        if (Array.isArray(payload.sources) && payload.sources.length > 0) {
                            const sourcesDiv = document.createElement('div');
                            sourcesDiv.className = 'sources-container';
                            const sourcesTitle = document.createElement('div');
                            sourcesTitle.className = 'sources-title';
                            sourcesTitle.innerText = 'Sources:';
                            sourcesDiv.appendChild(sourcesTitle);

                            const ul = document.createElement('ul');
                            ul.className = 'sources-list';
                            payload.sources.forEach(src => {
                                const li = document.createElement('li');
                                li.innerText = src;
                                ul.appendChild(li);
                            });
                            sourcesDiv.appendChild(ul);
                            assistantMessageDiv.querySelector('.message-content').appendChild(sourcesDiv);
                        }

                        if (payload.timestamp) {
                            const timeDiv = document.createElement('div');
                            timeDiv.className = 'timestamp';
                            timeDiv.innerText = `Generated at: ${payload.timestamp}`;
                            assistantMessageDiv.querySelector('.message-content').appendChild(timeDiv);
                        }

                    } else if (payload.type === 'error') {
                        throw new Error(payload.message || 'Streaming error');
                    }
                }
            }

            if (!hasDoneEvent) {
                // Fallback if done event was not present
                removeTypingIndicator();
            }

        } catch (error) {
            console.error('API Error:', error);
            removeTypingIndicator();
            const userFriendlyMessage = "Chatbot is facing some issues for now. Please try again later.";
            if (assistantMessageDiv) {
                assistantContentDiv.innerText = userFriendlyMessage;
            } else {
                addMessage('assistant', userFriendlyMessage);
            }
        } finally {
            isWaitingForResponse = false;
            sendBtn.disabled = false;
            sendBtn.classList.remove('loading');
            chatInput.disabled = false;
            chatInput.focus();
        }
    };

    // Event listeners
    sendBtn.addEventListener('click', () => {
        handleSend(chatInput.value);
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend(chatInput.value);
        }
    });

    sampleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            handleSend(btn.innerText);
        });
    });

    // Sidebar toggle
    if (sidebar && sidebarToggleBtn && appContainer) {
        const collapseIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M15 18L9 12L15 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        const expandIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

        sidebarToggleBtn.addEventListener('click', () => {
            const isCollapsed = sidebar.classList.toggle('collapsed');
            appContainer.classList.toggle('sidebar-collapsed', isCollapsed);
            sidebarToggleBtn.innerHTML = isCollapsed ? expandIcon : collapseIcon;
            sidebarToggleBtn.setAttribute('aria-expanded', String(!isCollapsed));
        });

        // Initialize icon
        sidebarToggleBtn.innerHTML = collapseIcon;
    }
});
