import { cn } from "@/lib/utils"
import type { ChatMessage as ChatMessageType } from "@/lib/types/session"
import { Bot, User } from "lucide-react"
import { MarkdownMessage } from "./markdown-message"
import { ToolCallCard } from "./tool-call-card"

interface ChatMessageProps {
  message: ChatMessageType
  streamingContent?: string
  isStreaming?: boolean
  streamingStatusText?: string
}

/** Render a single chat message bubble. */
export function ChatMessage({
  message,
  streamingContent,
  isStreaming = false,
  streamingStatusText = "正在生成…",
}: ChatMessageProps) {
  const isUser = message.role === "user"
  const displayContent = streamingContent ?? message.content

  return (
    <div
      className={cn(
        "flex w-full gap-3",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div
        className={cn(
          "flex min-w-0 flex-col gap-1",
          isUser ? "max-w-[75%] items-end" : "w-full items-start"
        )}
      >
        <div
          className={cn(
            "max-w-full space-y-2 text-sm",
            isUser
              ? "rounded-2xl bg-primary px-4 py-3 text-primary-foreground"
              : "w-full min-w-0 text-card-foreground"
          )}
        >
          {displayContent ? (
            <div className="break-words">
              {isUser ? (
                <span className="whitespace-pre-wrap">{displayContent}</span>
              ) : (
                <MarkdownMessage content={displayContent} />
              )}
            </div>
          ) : null}
          {isStreaming ? (
            <div className="text-xs text-muted-foreground">
              {streamingStatusText}
            </div>
          ) : null}
          {message.tool_calls && message.tool_calls.length > 0 ? (
            <div className="space-y-2">
              {message.tool_calls.map((toolCall) => (
                <ToolCallCard key={toolCall.id} toolCall={toolCall} />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
