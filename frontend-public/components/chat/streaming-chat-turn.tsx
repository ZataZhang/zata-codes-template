import { Wrench } from "lucide-react"

import { ChatMessage } from "@/components/chat/chat-message"
import { ToolCallCard } from "@/components/chat/tool-call-card"
import type {
  ChatMessage as ChatMessageType,
  ToolCall,
} from "@/lib/types/session"

export type StreamingChatBlock =
  { kind: "text"; content: string } | { kind: "tool"; toolCall: ToolCall }

interface StreamingChatTurnProps {
  message: ChatMessageType
  blocks: StreamingChatBlock[]
  isStreaming?: boolean
  streamingStatusText?: string
}

/** 向流式块序列追加文本，并保持文本与工具调用的真实发生顺序。 */
export function appendStreamingDelta(
  blocks: StreamingChatBlock[],
  deltaText: string
): StreamingChatBlock[] {
  const nextBlocks = blocks.slice()
  const lastBlockIndex = nextBlocks.length - 1
  const lastBlock = nextBlocks[lastBlockIndex]
  if (lastBlock?.kind === "text") {
    nextBlocks[lastBlockIndex] = {
      kind: "text",
      content: lastBlock.content + deltaText,
    }
  } else {
    nextBlocks.push({ kind: "text", content: deltaText })
  }
  return nextBlocks
}

/** 新增或更新一个工具调用块。 */
export function upsertStreamingTool(
  blocks: StreamingChatBlock[],
  toolCall: ToolCall
): StreamingChatBlock[] {
  const existingBlockIndex = blocks.findIndex(
    (block) => block.kind === "tool" && block.toolCall.id === toolCall.id
  )
  if (existingBlockIndex < 0) {
    return [...blocks, { kind: "tool", toolCall }]
  }
  return blocks.map((block, blockIndex) =>
    blockIndex === existingBlockIndex ? { kind: "tool", toolCall } : block
  )
}

/** 按 SSE 事件顺序交错展示助手文本和工具调用。 */
export function StreamingChatTurn({
  message,
  blocks,
  isStreaming = false,
  streamingStatusText = "正在生成…",
}: StreamingChatTurnProps) {
  if (blocks.length === 0) {
    return (
      <ChatMessage
        message={message}
        streamingContent=""
        isStreaming={isStreaming}
        streamingStatusText={streamingStatusText}
      />
    )
  }

  return (
    <div className="space-y-3">
      {blocks.map((block, blockIndex) =>
        block.kind === "tool" ? (
          <div
            key={`tool-${block.toolCall.id}`}
            className="flex w-full justify-start gap-3"
          >
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
              <Wrench className="size-4" />
            </div>
            <div className="flex w-full min-w-0 flex-col items-start gap-1">
              <ToolCallCard toolCall={block.toolCall} />
            </div>
          </div>
        ) : (
          <ChatMessage
            key={`text-${message.id}-${blockIndex}`}
            message={message}
            streamingContent={block.content}
            isStreaming={isStreaming && blockIndex === blocks.length - 1}
            streamingStatusText={streamingStatusText}
          />
        )
      )}
    </div>
  )
}
