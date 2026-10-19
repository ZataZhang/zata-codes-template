/** 帮助文章的列表项；正文不含 frontmatter。 */
export type HelpArticle = {
  slug: string;
  category: string;
  order: number;
  title: string;
  summary: string;
  bodyMarkdown: string;
};

const FRONTMATTER_PATTERN = /^---\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/;
const SCALAR_FIELD_PATTERN = /^(slug|category|order|title|summary):\s*(.+?)\s*$/gm;

// 正文唯一来源是仓库里的文章目录；构建期的 help-static 插件读同一目录发布 .md 与 llms.txt。
// glob 路径相对本文件：按前端子目录深度调整 `../` 的层数，并与插件的 helpDirectory 指向同一处。
const helpMarkdownSourceByPath = import.meta.glob(
  ["../../../../docs/help/**/*.md", "!../../../../docs/help/**/index.md"],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

/** 解析带 frontmatter 的文章原文；缺少必填字段时返回 null。页面只需要标量字段，嵌套字段由构建插件校验。 */
function parseHelpArticle(markdownSourceText: string): HelpArticle | null {
  const frontmatterMatch = markdownSourceText.match(FRONTMATTER_PATTERN);
  if (!frontmatterMatch) {
    return null;
  }
  const scalarFieldByName = Object.fromEntries(
    [...frontmatterMatch[1].matchAll(SCALAR_FIELD_PATTERN)].map((fieldMatch) => [fieldMatch[1], fieldMatch[2]]),
  );
  const { slug, category, title, summary } = scalarFieldByName;
  if (!slug || !category || !title || !summary) {
    return null;
  }
  return {
    slug,
    category,
    title,
    summary,
    order: Number(scalarFieldByName.order),
    bodyMarkdown: markdownSourceText.slice(frontmatterMatch[0].length),
  };
}

/** 全部帮助文章，按 order 升序。 */
export const helpArticleList: HelpArticle[] = Object.values(helpMarkdownSourceByPath)
  .map(parseHelpArticle)
  .filter((article): article is HelpArticle => article !== null)
  .sort((articleA, articleB) => articleA.order - articleB.order);

/** 按 slug 查找文章，不存在返回 undefined。 */
export function findHelpArticle(slug: string): HelpArticle | undefined {
  return helpArticleList.find((article) => article.slug === slug);
}
