"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Send, User } from "lucide-react";
import { QuantChatAvatar } from "@/components/QuantChatAvatar";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello! I'm your AI recruiting assistant. I can help you with questions about your application, schedule interviews, or provide updates on your status. How can I help you today?",
      timestamp: new Date(Date.now() - 3600000),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages([...messages, userMessage]);
    setInput("");
    setLoading(true);

    // Simulate AI response (in production, call EngagementAgent)
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: getAIResponse(input),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
      setLoading(false);
    }, 1500);
  };

  const getAIResponse = (userInput: string): string => {
    const input = userInput.toLowerCase();
    
    if (input.includes("status") || input.includes("application")) {
      return "Your application for Senior Software Engineer is currently in the screening stage. Our team is reviewing your profile and will reach out within 2-3 business days.";
    }
    if (input.includes("interview") || input.includes("schedule")) {
      return "I'd be happy to help schedule your interview! I have the following time slots available this week: Monday 2PM, Wednesday 10AM, or Friday 3PM. Which works best for you?";
    }
    if (input.includes("salary") || input.includes("compensation")) {
      return "The compensation range for this position is $140,000 - $180,000 plus equity and comprehensive benefits. The final offer will be determined based on your experience and interview performance.";
    }
    if (input.includes("remote") || input.includes("location")) {
      return "Yes, this position offers hybrid/remote options. Our San Francisco office is available for collaboration, but remote work is fully supported.";
    }
    
    return "Thank you for your question! Our recruiting team will review this and get back to you shortly. In the meantime, you can check your application status in the dashboard or ask me about scheduling, compensation, or the interview process.";
  };

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">AI Recruiter Chat</h2>
          <p className="text-muted-foreground">
            Powered by EngagementAgent using GPT-4o
          </p>
        </div>
        <Badge className="bg-brand-teal text-white">
          <div className="h-2 w-2 bg-white rounded-full mr-2 animate-pulse" />
          Online
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-[300px_1fr]">
        {/* Conversation List */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent Conversations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              { name: "Alice Johnson", lastMessage: "When can I start?", unread: 2 },
              { name: "Bob Smith", lastMessage: "Interview confirmed", unread: 0 },
              { name: "Carol Davis", lastMessage: "Thank you!", unread: 0 },
            ].map((conv, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg cursor-pointer transition-colors ${
                  index === 0 ? "bg-primary/10 border border-primary/20" : "hover:bg-muted"
                }`}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{conv.name}</p>
                  {conv.unread > 0 && (
                    <Badge variant="default" className="h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
                      {conv.unread}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground truncate mt-1">
                  {conv.lastMessage}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Chat Window */}
        <Card className="flex flex-col h-[600px]">
          <CardHeader className="border-b">
            <div className="flex items-center gap-3">
              <Avatar>
                <AvatarFallback className="bg-primary text-primary-foreground">
                  AJ
                </AvatarFallback>
              </Avatar>
              <div>
                <CardTitle className="text-base">Alice Johnson</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Application: Senior Software Engineer
                </p>
              </div>
            </div>
          </CardHeader>

          {/* Messages */}
          <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 ${
                  message.role === "user" ? "flex-row-reverse" : ""
                }`}
              >
                {message.role === "assistant" ? (
                  <QuantChatAvatar size="xs" />
                ) : (
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-muted">
                      <User className="h-4 w-4" />
                    </AvatarFallback>
                  </Avatar>
                )}
                <div
                  className={`flex-1 ${
                    message.role === "user" ? "flex justify-end" : ""
                  }`}
                >
                  <div
                    className={`inline-block p-3 rounded-lg max-w-[80%] ${
                      message.role === "assistant"
                        ? "bg-muted"
                        : "bg-primary text-primary-foreground"
                    }`}
                  >
                    <p className="text-sm">{message.content}</p>
                    <p className="text-xs opacity-70 mt-1">
                      {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <QuantChatAvatar size="xs" />
                <div className="flex items-center gap-1 p-3 rounded-lg bg-muted">
                  <div className="h-2 w-2 bg-primary rounded-full animate-bounce" />
                  <div className="h-2 w-2 bg-primary rounded-full animate-bounce delay-100" />
                  <div className="h-2 w-2 bg-primary rounded-full animate-bounce delay-200" />
                </div>
              </div>
            )}
          </CardContent>

          {/* Input */}
          <div className="border-t p-4">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex gap-2"
            >
              <Input
                placeholder="Type your message..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
              />
              <Button type="submit" disabled={loading || !input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </Card>
      </div>
    </div>
  );
}

