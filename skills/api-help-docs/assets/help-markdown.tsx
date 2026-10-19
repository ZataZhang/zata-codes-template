import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// 样式类名按项目的 CSS 方案替换（这里是 Tailwind）。没有 typography 插件时，逐元素映射最省事。
const MARKDOWN_COMPONENTS: Components = {
  h1: ({ node: _node, ...props }) => <h1 className="mb-4 text-3xl font-semibold" {...props} />,
  h2: ({ node: _node, ...props }) => <h2 className="mt-10 mb-3 border-t pt-6 text-2xl font-semibold" {...props} />,
  h3: ({ node: _node, ...props }) => <h3 className="mt-6 mb-2 text-lg font-semibold" {...props} />,
  p: ({ node: _node, ...props }) => <p className="my-3 leading-7" {...props} />,
  ul: ({ node: _node, ...props }) => <ul className="my-3 list-disc space-y-1 ps-6" {...props} />,
  ol: ({ node: _node, ...props }) => <ol className="my-3 list-decimal space-y-1 ps-6" {...props} />,
  blockquote: ({ node: _node, ...props }) => <blockquote className="my-4 border-s-4 px-4 py-2 text-sm" {...props} />,
  pre: ({ node: _node, ...props }) => <pre className="my-4 overflow-x-auto rounded-md p-4 text-sm" {...props} />,
  table: ({ node: _node, ...props }) => (
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm" {...props} />
    </div>
  ),
  th: ({ node: _node, ...props }) => <th className="border px-3 py-2 text-start font-medium" {...props} />,
  td: ({ node: _node, ...props }) => <td className="border px-3 py-2 align-top" {...props} />,
};

/**
 * 把文章里指向兄弟文章的相对 `.md` 链接改写成站内 `/help/<slug>` 路径。
 * 不改写的话，页面里的 `[x](other.md)` 会指向不存在的地址。
 *
 * @param href 正文里的链接地址。
 * @param articleSlug 当前文章的 slug，用来确定相对目录。
 */
function resolveHelpHref(href: string | undefined, articleSlug: string): string | undefined {
  if (!href || !href.endsWith(".md") || /^[a-z]+:|^\//.test(href)) {
    return href;
  }
  const articleDirectory = articleSlug.split("/").slice(0, -1);
  return `/help/${[...articleDirectory, href.replace(/\.md$/, "")].join("/")}`;
}

/** 渲染帮助文章的 Markdown 正文（GFM 表格、代码块）。 */
export function HelpMarkdown({ bodyMarkdown, articleSlug }: { bodyMarkdown: string; articleSlug: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        ...MARKDOWN_COMPONENTS,
        a: ({ node: _node, href, ...props }) => (
          <a className="underline underline-offset-4" href={resolveHelpHref(href, articleSlug)} {...props} />
        ),
      }}
    >
      {bodyMarkdown}
    </ReactMarkdown>
  );
}
