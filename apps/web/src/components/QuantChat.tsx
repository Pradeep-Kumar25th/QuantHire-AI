"use client";

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Minimize2, Maximize2, Settings, Shield, Zap, Database, X } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import QuantChatLogo from './QuantChatLogo';
import ChatMessage from './ChatMessage';
import TypingIndicator from './TypingIndicator';
import { getApiErrorMessage } from '@/lib/api-errors';
import {
  AZURE_LLM_LABEL,
  AZURE_VECTOR_STORE_LABEL,
} from '@/lib/azure-messages';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'assistant';
  timestamp: string;
  processingMethod?: string;
  securityStatus?: string;
  queryType?: string;
}

interface QuantChatProps {
  onClose?: () => void;
}

const QuantChat: React.FC<QuantChatProps> = ({ onClose }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Hello! I\'m QuantChat, your enterprise AI assistant. I can help you with QuantHire-specific queries about candidates, jobs, and skills, or answer general knowledge questions. How can I assist you today?',
      sender: 'assistant',
      timestamp: new Date().toLocaleTimeString(),
      processingMethod: 'WELCOME',
      securityStatus: 'SECURE',
      queryType: 'WELCOME'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(true); // Start minimized
  const [isClosed, setIsClosed] = useState(false); // Can be closed completely
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const processQuery = useCallback(async (query: string) => {
    setIsLoading(true);

    const userMessage: Message = {
      id: Date.now().toString(),
      text: query,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);

    try {
      const { api } = await import('@/lib/api');
      const response = await api.quantchat.chat({ message: query });
      const data = response.data;
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: data.response,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString(),
        processingMethod: data.processing_method,
        securityStatus: data.security_status,
        queryType: data.query_type
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: unknown) {
      console.error('Error:', error);
      const errorText = getApiErrorMessage(
        error,
        "I'm experiencing technical difficulties. Please try again in a moment.",
      );
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: errorText,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString(),
        processingMethod: 'ERROR',
        securityStatus: 'ERROR',
        queryType: 'ERROR'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{
        message?: string;
        expand?: boolean;
        autoSend?: boolean;
      }>).detail;
      if (detail?.expand) {
        setIsClosed(false);
        setIsMinimized(false);
      }
      if (detail?.message) {
        if (detail.autoSend) {
          window.setTimeout(() => {
            void processQuery(detail.message!.trim());
          }, 200);
        } else {
          setInput(detail.message);
          window.setTimeout(() => inputRef.current?.focus(), 120);
        }
      }
    };
    window.addEventListener("quanthire:quantchat-open", handler);
    return () => window.removeEventListener("quanthire:quantchat-open", handler);
  }, [processQuery]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      processQuery(input.trim());
      setInput('');
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: '1',
        text: 'Hello! I\'m QuantChat, your enterprise AI assistant. I can help you with QuantHire-specific queries about candidates, jobs, and skills, or answer general knowledge questions. How can I assist you today?',
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString(),
        processingMethod: 'WELCOME',
        securityStatus: 'SECURE',
        queryType: 'WELCOME'
      }
    ]);
  };

  // If closed, show a small button to reopen
  if (isClosed) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          onClick={() => {
            setIsClosed(false);
            setIsMinimized(false);
          }}
          className="bg-transparent hover:bg-transparent border-0 p-0 rounded-full h-[68px] w-[68px] shadow-2xl hover:shadow-3xl hover:scale-110 transition-all duration-300"
          title="Open QuantChat"
        >
          <QuantChatLogo size="lg" variant="badge" />
        </Button>
      </div>
    );
  }

  // If minimized, show floating icon
  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          onClick={() => setIsMinimized(false)}
          className="bg-transparent hover:bg-transparent border-0 p-0 rounded-full h-[68px] w-[68px] shadow-2xl hover:shadow-3xl hover:scale-110 transition-all duration-300"
          title="Open QuantChat"
        >
          <QuantChatLogo size="lg" variant="badge" />
        </Button>
      </div>
    );
  }

  return (
    <div 
      className="fixed right-4 z-50 w-96 animate-in slide-in-from-bottom-4 fade-in duration-300" 
      style={{ 
        top: '0.5rem',
        bottom: '0rem',
        height: 'calc(100vh - 0.5rem)',
        maxHeight: 'calc(100vh - 0.5rem)'
      }}
    >
      <Card className="h-full flex flex-col bg-gradient-to-br from-white via-brand-light to-brand-light/80 border border-brand-gray/40 shadow-2xl rounded-2xl overflow-hidden backdrop-blur-xl">
        {/* Header */}
        <CardHeader className="bg-gradient-to-r from-brand-red via-brand-gold to-brand-teal text-white px-4 py-2 flex-shrink-0 shadow-lg border-b border-white/5" style={{ borderWidth: '1px' }}>
          <div className="flex items-center justify-between">
            <div className="flex flex-1 min-w-0 items-center py-1">
              <QuantChatLogo size="md" variant="nav" className="max-w-[min(100%,220px)]" />
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSettings(!showSettings)}
                className="text-white hover:bg-white/20 h-6 w-6 p-0"
                title="Settings"
              >
                <Settings className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsMinimized(true)}
                className="text-white hover:bg-white/20 h-6 w-6 p-0"
                title="Minimize"
              >
                <Minimize2 className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsMinimized(true);
                  setIsClosed(true);
                }}
                className="text-white hover:bg-brand-red/30 h-6 w-6 p-0 border border-brand-red/60 rounded hover:border-brand-red"
                title="Close"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
          </div>
          
          {/* Settings Panel */}
          {showSettings && (
            <div className="mt-3 p-3 bg-white/10 rounded-lg backdrop-blur-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Settings</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowSettings(false)}
                  className="text-white hover:bg-white/20 h-6 w-6 p-0"
                >
                  <X className="w-3 h-3" />
                </Button>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs">
                  <Shield className="w-3 h-3 text-brand-teal" />
                  <span>Enterprise Security</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Database className="w-3 h-3 text-brand-gold" />
                  <span>{AZURE_VECTOR_STORE_LABEL}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Zap className="w-3 h-3 text-brand-red" />
                  <span>{AZURE_LLM_LABEL}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearChat}
                  className="w-full text-xs bg-white/20 border-white/30 text-white hover:bg-white/30"
                >
                  Clear Chat
                </Button>
              </div>
            </div>
          )}
        </CardHeader>

        {/* Messages Area */}
        <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-1">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-brand-gray/40 bg-gradient-to-r from-brand-light to-white flex-shrink-0 shadow-inner">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask QuantChat anything..."
                disabled={isLoading}
                className="flex-1 border-brand-gray/60 focus:border-brand-teal focus:ring-brand-teal rounded-xl shadow-sm"
              />
              <Button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="rounded-xl px-4 py-2 transition-all duration-200 disabled:opacity-50 shadow-lg hover:shadow-xl flex items-center justify-center gap-2"
              >
                <Send className="w-4 h-4" />
              </Button>
            </form>
            
            {/* Quick Actions */}
            <div className="mt-2 flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setInput("Find me Python developers")}
                className="text-xs bg-white border-brand-gray/60 hover:bg-brand-light/70"
              >
                Find Developers
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setInput("Analyze our candidates")}
                className="text-xs bg-white border-brand-gray/60 hover:bg-brand-light/70"
              >
                Analyze Candidates
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setInput("What's the weather today?")}
                className="text-xs bg-white border-brand-gray/60 hover:bg-brand-light/70"
              >
                General Question
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default QuantChat;