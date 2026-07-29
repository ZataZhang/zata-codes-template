import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface MarkdownMessageProps {
  content: string
}

/** 使用项目统一样式渲染聊天消息中的 Markdown。 */
export function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ children, ...props }) => (
          <a
            {...props}
            className="text-primary underline underline-offset-4"
            target="_blank"
            rel="noreferrer"
          >
            {children}
          </a>
        ),
        code: ({ children, className, ...props }) => (
          <code
            {...props}
            className={
              className
                ? `${className} rounded bg-muted px-1 py-0.5`
                : "rounded bg-muted px-1 py-0.5"
            }
          >
            {children}
          </code>
        ),
        pre: ({ children }) => (
          <pre className="max-w-full overflow-x-auto rounded-lg bg-muted p-3 text-xs">
            {children}
          </pre>
        ),
        ul: ({ children }) => (
          <ul className="list-disc space-y-1 pl-5">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal space-y-1 pl-5">{children}</ol>
        ),
        p: ({ children }) => (
          <p className="my-2 first:mt-0 last:mb-0">{children}</p>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
