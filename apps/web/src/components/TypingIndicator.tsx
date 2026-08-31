import React from 'react';
import { QuantChatAvatar } from './QuantChatAvatar';

export const TypingIndicator: React.FC = () => {
  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-3">
        <QuantChatAvatar size="xs" />

        {/* Typing Animation */}
        <div className="bg-white border border-brand-gray/40 rounded-2xl rounded-bl-md shadow-sm px-4 py-3">
          <div className="flex items-center gap-1">
            <span className="text-sm text-brand-dark/60">QuantChat is typing</span>
            <div className="flex gap-1">
              <div className="w-1 h-1 bg-brand-gray rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-1 h-1 bg-brand-gray rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-1 h-1 bg-brand-gray rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;
