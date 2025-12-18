"use client";

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  decision?: string;
  confidence?: number;
  reportUrl?: string;
}

export default function ChatUI() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '👋 Welcome to **PharmaAI**! I\'m your AI research assistant for drug repurposing and innovation opportunities.\n\nAsk me questions like:\n- "Find repurposing opportunities for Montelukast"\n- "Analyze market potential for Metformin in PCOS"\n- "What are the patent risks for Aspirin formulations?"',
      timestamp: new Date().toISOString(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputValue,
          conversation_history: messages,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.message,
        timestamp: new Date().toISOString(),
        decision: data.decision,
        confidence: data.confidence,
        reportUrl: data.report_url,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: '❌ Sorry, I encountered an error. Please make sure the backend server is running on http://localhost:8000',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const getDecisionBadgeColor = (decision?: string) => {
    switch (decision) {
      case 'GO':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'PARTIAL_GO':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'NO_GO':
        return 'bg-red-100 text-red-800 border-red-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <div className="bg-white shadow-md border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold text-gray-900">
            <span className="text-indigo-600">Pharma</span>AI
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Drug Repurposing Research Assistant powered by Agentic AI
          </p>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-3xl rounded-lg px-4 py-3 shadow-sm ${
                  message.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-gray-900 border border-gray-200'
                }`}
              >
                {/* Decision Badge */}
                {message.decision && (
                  <div className="mb-2 flex items-center gap-2">
                    <span
                      className={`px-3 py-1 text-xs font-semibold rounded-full border ${getDecisionBadgeColor(
                        message.decision
                      )}`}
                    >
                      {message.decision}
                    </span>
                    {message.confidence !== undefined && (
                      <span className="text-xs text-gray-600">
                        Confidence: {message.confidence}%
                      </span>
                    )}
                  </div>
                )}

                {/* Message Content */}
                <div
                  className={`prose prose-sm max-w-none ${
                    message.role === 'user'
                      ? 'prose-invert'
                      : 'prose-gray'
                  }`}
                >
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {/* Report Link */}
                {message.reportUrl && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <a
                      href={`http://localhost:8000${message.reportUrl}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                      Download Full Report
                    </a>
                  </div>
                )}

                {/* Timestamp */}
                <div
                  className={`text-xs mt-2 ${
                    message.role === 'user'
                      ? 'text-indigo-200'
                      : 'text-gray-500'
                  }`}
                  suppressHydrationWarning
                >
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white rounded-lg px-4 py-3 shadow-sm border border-gray-200">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce delay-100"></div>
                    <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce delay-200"></div>
                  </div>
                  <span className="text-sm text-gray-600">
                    Analyzing with AI agents...
                  </span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Form */}
      <div className="bg-white border-t border-gray-200 px-4 py-4 shadow-lg">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about drug repurposing opportunities..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? (
                <svg
                  className="animate-spin h-5 w-5"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
              ) : (
                'Send'
              )}
            </button>
          </form>
          
          {/* Example prompts */}
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-gray-500">Try:</span>
            {[
              'Montelukast repurposing',
              'Metformin market analysis',
              'Aspirin patent landscape'
            ].map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => setInputValue(prompt)}
                className="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
