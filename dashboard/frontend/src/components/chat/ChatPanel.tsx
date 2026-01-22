/**
 * Chat panel component with Claude integration
 */

import { useState, useRef, useEffect } from 'react';
import { Send, StopCircle, Trash2 } from 'lucide-react';
import { useStreamingChat } from '@/hooks';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ScrollArea,
} from '@/components/ui';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/types';

interface ChatPanelProps {
  projectName: string;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[80%] rounded-lg px-4 py-2',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        )}
      >
        <p className="whitespace-pre-wrap text-sm">{message.content}</p>
      </div>
    </div>
  );
}

export function ChatPanel({ projectName }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const {
    messages,
    currentResponse,
    isStreaming,
    sendMessage,
    stopStreaming,
    clearMessages,
  } = useStreamingChat(projectName);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, currentResponse]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    sendMessage(input);
    setInput('');
  };

  return (
    <Card className="h-[600px] flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle>Chat with Claude</CardTitle>
          <Button variant="ghost" size="sm" onClick={clearMessages}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col overflow-hidden">
        {/* Messages */}
        <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
          <div className="space-y-4">
            {messages.map((message, index) => (
              <MessageBubble key={index} message={message} />
            ))}
            {isStreaming && currentResponse && (
              <MessageBubble
                message={{
                  role: 'assistant',
                  content: currentResponse + '...',
                }}
              />
            )}
            {messages.length === 0 && !isStreaming && (
              <div className="text-center text-muted-foreground py-8">
                <p>Start a conversation with Claude</p>
                <p className="text-sm mt-2">
                  Ask questions about this project or run commands
                </p>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex items-center space-x-2 mt-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 px-3 py-2 border rounded-md"
            disabled={isStreaming}
          />
          {isStreaming ? (
            <Button
              type="button"
              variant="destructive"
              onClick={stopStreaming}
            >
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
