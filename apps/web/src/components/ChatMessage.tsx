"use client";

import React, { useState, useEffect } from 'react';
import { User, Shield, Zap, Database } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { QuantChatAvatar } from './QuantChatAvatar';

interface ChatMessageProps {
  message: {
    id: string;
    text: string;
    sender: 'user' | 'assistant';
    timestamp: string;
    processingMethod?: string;
    securityStatus?: string;
    queryType?: string;
  };
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);
  const isUser = message.sender === 'user';
  
  const getSecurityIcon = () => {
    if (message.queryType === 'GENERAL_KNOWLEDGE') {
      return <Zap className="w-3 h-3 text-brand-gold" />;
    }
    return <Shield className="w-3 h-3 text-brand-teal" />;
  };

  const getSecurityText = () => {
    if (message.queryType === 'GENERAL_KNOWLEDGE') {
      return 'Direct API';
    }
    return 'Hybrid Secure';
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`flex max-w-[80%] ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start gap-3`}>
        {/* Avatar */}
        <div className="flex-shrink-0">
          {isUser ? (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-red to-cta-end ring-1 ring-white/20 shadow-sm">
              <User className="h-4 w-4 text-white" />
            </div>
          ) : (
            <QuantChatAvatar size="xs" />
          )}
        </div>

        {/* Message Content */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
          {/* Message Bubble */}
          <div className={`px-4 py-3 rounded-2xl ${
            isUser
              ? 'bg-gradient-to-br from-brand-red to-cta-end text-white rounded-br-md'
              : 'bg-white border border-brand-gray/40 text-brand-dark rounded-bl-md shadow-sm'
          }`}>
            {isUser ? (
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
            ) : (
              <div className="text-sm leading-relaxed prose prose-sm max-w-none
                prose-headings:text-brand-dark prose-headings:font-bold prose-headings:mt-3 prose-headings:mb-2
                prose-h1:text-lg prose-h1:border-b prose-h1:border-brand-gray/30 prose-h1:pb-2
                prose-h2:text-base prose-h3:text-sm
                prose-p:my-1.5 prose-p:leading-relaxed
                prose-ul:my-2 prose-ul:pl-4 prose-li:my-0.5
                prose-ol:my-2 prose-ol:pl-4
                prose-strong:text-brand-dark prose-strong:font-semibold
                prose-a:text-brand-teal prose-a:no-underline hover:prose-a:underline
                prose-hr:my-3 prose-hr:border-brand-gray/30
                prose-code:bg-brand-gray/20 prose-code:px-1 prose-code:rounded prose-code:text-brand-red
                prose-pre:bg-brand-gray/10 prose-pre:p-3 prose-pre:rounded-lg prose-pre:overflow-x-auto
              ">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.text}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {/* Message Metadata */}
          <div className={`flex items-center gap-2 mt-1 text-xs text-brand-dark/60 ${
            isUser ? 'flex-row-reverse' : 'flex-row'
          }`}>
            <span suppressHydrationWarning>{mounted && message.timestamp}</span>
            {!isUser && (
              <>
                <span>•</span>
                <div className="flex items-center gap-1">
                  {getSecurityIcon()}
                  <span className="text-xs">{getSecurityText()}</span>
                </div>
                {message.processingMethod && (
                  <>
                    <span>•</span>
                    <div className="flex items-center gap-1">
                      <Database className="w-3 h-3 text-brand-gray" />
                      <span className="text-xs">
                        {message.processingMethod === 'GENERAL_KNOWLEDGE_DIRECT' 
                          ? 'Direct' 
                          : 'Vector Search'
                        }
                      </span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
