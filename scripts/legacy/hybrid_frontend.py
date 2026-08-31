"""
QuantHire AI - Hybrid AI Assistant Frontend
============================================

Simple web interface to demonstrate the hybrid AI assistant
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="QuantHire AI - Hybrid Assistant Frontend")

@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Get the chat interface"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QuantHire AI - Hybrid Assistant</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }
            .header h1 {
                margin: 0;
                font-size: 2em;
            }
            .header p {
                margin: 10px 0 0 0;
                opacity: 0.9;
            }
            .chat-container {
                height: 400px;
                overflow-y: auto;
                padding: 20px;
                border-bottom: 1px solid #eee;
            }
            .message {
                margin: 10px 0;
                padding: 15px;
                border-radius: 10px;
                max-width: 80%;
            }
            .user-message {
                background: #e3f2fd;
                margin-left: auto;
                text-align: right;
            }
            .ai-message {
                background: #f5f5f5;
                margin-right: auto;
            }
            .system-message {
                background: #fff3e0;
                margin: 10px auto;
                text-align: center;
                font-style: italic;
                max-width: 90%;
            }
            .input-container {
                padding: 20px;
                display: flex;
                gap: 10px;
            }
            .input-field {
                flex: 1;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 25px;
                font-size: 16px;
                outline: none;
                transition: border-color 0.3s;
            }
            .input-field:focus {
                border-color: #667eea;
            }
            .send-button {
                padding: 12px 25px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                transition: transform 0.2s;
            }
            .send-button:hover {
                transform: translateY(-2px);
            }
            .status-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 5px;
            }
            .status-local {
                background: #4caf50;
            }
            .status-ai {
                background: #2196f3;
            }
            .examples {
                padding: 20px;
                background: #f8f9fa;
                border-top: 1px solid #eee;
            }
            .examples h3 {
                margin: 0 0 15px 0;
                color: #333;
            }
            .example-button {
                display: inline-block;
                margin: 5px;
                padding: 8px 15px;
                background: #e9ecef;
                border: none;
                border-radius: 20px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.3s;
            }
            .example-button:hover {
                background: #dee2e6;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 QuantHire AI Assistant</h1>
                <p>Hybrid Solution: Secure Local Processing + AI Assistant</p>
            </div>
            
            <div class="chat-container" id="chatContainer">
                <div class="system-message">
                    <strong>🛡️ Privacy Protected:</strong> Sensitive data is processed locally, general queries use AI
                </div>
                <div class="ai-message">
                    <span class="status-indicator status-ai"></span>
                    <strong>AI Assistant:</strong> Hello! I'm your QuantHire AI assistant. I can help with hiring questions, interview techniques, and recruitment best practices. Ask me anything!
                </div>
            </div>
            
            <div class="input-container">
                <input type="text" id="messageInput" class="input-field" placeholder="Ask me about hiring, interviews, or recruitment..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()" class="send-button">Send</button>
            </div>
            
            <div class="examples">
                <h3>💡 Try these examples:</h3>
                <button class="example-button" onclick="sendExample('What are the best practices for technical interviews?')">Technical Interview Tips</button>
                <button class="example-button" onclick="sendExample('How to improve candidate experience?')">Candidate Experience</button>
                <button class="example-button" onclick="sendExample('What are trending tech skills?')">Trending Skills</button>
                <button class="example-button" onclick="sendExample('Analyze John Smith resume with email john@example.com')">Resume Analysis (Local)</button>
                <button class="example-button" onclick="sendExample('How to reduce hiring bias?')">Reduce Bias</button>
            </div>
        </div>

        <script>
            async function sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                
                if (!message) return;
                
                // Add user message to chat
                addMessage(message, 'user');
                input.value = '';
                
                // Show typing indicator
                const typingId = addMessage('AI is thinking...', 'ai', true);
                
                try {
                    const response = await fetch('http://localhost:8003/api/v1/hybrid/ai-chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ message: message })
                    });
                    
                    const data = await response.json();
                    
                    // Remove typing indicator
                    removeMessage(typingId);
                    
                    // Add AI response
                    const statusClass = data.processed_locally ? 'status-local' : 'status-ai';
                    const statusText = data.processed_locally ? 'Local Processing' : 'AI Response';
                    
                    addMessage(`<span class="status-indicator ${statusClass}"></span><strong>${statusText}:</strong> ${data.response}`, 'ai');
                    
                } catch (error) {
                    removeMessage(typingId);
                    addMessage('Sorry, I encountered an error. Please try again.', 'ai');
                    console.error('Error:', error);
                }
            }
            
            function sendExample(message) {
                document.getElementById('messageInput').value = message;
                sendMessage();
            }
            
            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            }
            
            function addMessage(content, type, isTemporary = false) {
                const chatContainer = document.getElementById('chatContainer');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}-message`;
                messageDiv.innerHTML = content;
                
                if (isTemporary) {
                    messageDiv.id = 'temp-' + Date.now();
                }
                
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
                
                return messageDiv.id;
            }
            
            function removeMessage(id) {
                const element = document.getElementById(id);
                if (element) {
                    element.remove();
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    print("=" * 80)
    print("🌐 QuantHire AI - Hybrid Assistant Frontend Starting...")
    print("=" * 80)
    print("✅ Web Interface: http://localhost:8004")
    print("✅ Hybrid AI Backend: http://localhost:8003")
    print("✅ Secure Local Processing: Port 8001")
    print("✅ Advanced Local AI: Port 8002")
    print("=" * 80)
    
    uvicorn.run(app, host="0.0.0.0", port=8004)

