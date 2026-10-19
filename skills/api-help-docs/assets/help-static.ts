import fs from "node:fs";
import path from "node:path";

import { parse as parseYaml } from "yaml";
import type { Plugin, ResolvedConfig } from "vite";

/** 插件选项。除 siteTitle 外都有默认值；没有 OpenAPI 公开地址时不要填 openApiUrl。 */
export type HelpStaticOptions = {
  /** llms.txt 的一级标题，例如 "<产品名> 帮助中心"。 */
  siteTitle: string;
  /** llms.txt 标题下的一句话说明。 */
  siteDescription: string;
  /** 文章目录，相对 Vite root。默认 "../docs/help"，按前端子目录深度调整（如 "../../docs/help"）。 */
  helpDirectory?: string;
  /**
   * 机器可读契约的公开地址，例如 "/api/openapi.json"。默认不写。
   * 只有确认该 OpenAPI 本来就面向外部公开时才填：它会列出后端的全部路由，
   * 含内部与管理端接口，写进 llms.txt 等于主动向外部推广整个接口面。
   */
  openApiUrl?: string;
  /** 是否要求 frontmatter 带 sections 且与正文 `##` 标题逐一一致。默认 true。 */
  requireSections?: boolean;
};

type HelpStaticArticle = {
  slug: string;
  category: string;
  order: number;
  title: string;
  summary: string;
  markdownSourceText: string;
};

const FRONTMATTER_PATTERN = /^---\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/;
const SECOND_LEVEL_HEADING_PATTERN = /^## (.+?)\s*$/gm;

/** 递归列出目录下除 index.md 外的全部 Markdown 文件。 */
function listMarkdownPath(directoryPath: string): string[] {
  if (!fs.existsSync(directoryPath)) {
    return [];
  }
  return fs.readdirSync(directoryPath, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md") && entry.name !== "index.md")
    .map((entry) => path.join(entry.parentPath, entry.name));
}

/** 读取并校验全部文章：必填字段、slug/order 唯一、（可选）sections 与正文 `##` 标题一致。 */
function readHelpStaticArticleList(helpDirectoryPath: string, requireSections: boolean): HelpStaticArticle[] {
  const articleList = listMarkdownPath(helpDirectoryPath).map((markdownPath) => {
    const markdownSourceText = fs.readFileSync(markdownPath, "utf-8");
    const frontmatterMatch = markdownSourceText.match(FRONTMATTER_PATTERN);
    const metadata = frontmatterMatch ? parseYaml(frontmatterMatch[1]) : null;
    if (
      !metadata
      || typeof metadata.slug !== "string"
      || typeof metadata.title !== "string"
      || typeof metadata.summary !== "string"
      || typeof metadata.category !== "string"
      || typeof metadata.order !== "number"
    ) {
      throw new Error(`帮助文章 ${markdownPath} 缺少发布所需的 frontmatter 字段。`);
    }
    if (requireSections) {
      if (!Array.isArray(metadata.sections)) {
        throw new Error(`帮助文章 ${markdownPath} 缺少 frontmatter sections。`);
      }
      const sectionTitleList = metadata.sections.map((section: { title: string }) => section.title);
      const headingTitleList = [...markdownSourceText.matchAll(SECOND_LEVEL_HEADING_PATTERN)]
        .map((headingMatch) => headingMatch[1]);
      if (sectionTitleList.join("\n") !== headingTitleList.join("\n")) {
        throw new Error(`帮助文章 ${markdownPath} 的 frontmatter sections 与正文 ## 标题不一致。`);
      }
    }
    return {
      slug: metadata.slug,
      category: metadata.category,
      order: metadata.order,
      title: metadata.title,
      summary: metadata.summary,
      markdownSourceText,
    };
  });
  for (const uniqueField of ["slug", "order"] as const) {
    const valueList = articleList.map((article) => article[uniqueField]);
    if (new Set(valueList).size !== valueList.length) {
      throw new Error(`帮助文章的 ${uniqueField} 必须唯一。`);
    }
  }
  return articleList.sort((articleA, articleB) => articleA.order - articleB.order);
}

/** 生成 llms.txt：按分类列出每篇文章的 .md 直链与摘要。 */
function buildLlmsIndex(articleList: HelpStaticArticle[], basePath: string, options: HelpStaticOptions): string {
  const lineList = [`# ${options.siteTitle}`, "", `> ${options.siteDescription}`, ""];
  for (const categoryName of new Set(articleList.map((article) => article.category))) {
    lineList.push(`## ${categoryName}`, "");
    for (const article of articleList.filter((item) => item.category === categoryName)) {
      lineList.push(`- [${article.title}](${basePath}help/${article.slug}.md): ${article.summary}`);
    }
    lineList.push("");
  }
  lineList.push("## 合订本", "");
  if (options.openApiUrl) {
    lineList.push(`- [OpenAPI 契约](${options.openApiUrl}): 全部 HTTP 接口的方法、路径与参数。`);
  }
  lineList.push(
    `- [全部文章合订本](${basePath}llms-full.txt): 上述全部文章的 Markdown 原文，适合一次读取。`,
    "",
  );
  return lineList.join("\n");
}

/**
 * 构建时把帮助文章的 Markdown 原文发布为静态文件，便于不执行 JS 的 agent 读取。
 *
 * 产物：`help/<slug>.md`、`llms.txt`、`llms-full.txt`。正文来源与产品内帮助页一致，
 * 不在此处另存副本。文章集为空时直接让构建失败。
 */
export function helpStaticPlugin(options: HelpStaticOptions): Plugin {
  let config: ResolvedConfig | undefined;
  return {
    name: "help-static",
    apply: "build",
    configResolved(resolvedConfig) {
      config = resolvedConfig;
    },
    writeBundle(outputOptions) {
      if (!config) {
        return;
      }
      const helpDirectoryPath = path.resolve(config.root, options.helpDirectory ?? "../docs/help");
      const articleList = readHelpStaticArticleList(helpDirectoryPath, options.requireSections ?? true);
      if (articleList.length === 0) {
        // 空集意味着构建上下文缺少文章目录（如 Docker 上下文不含），静默跳过会上线空帮助中心。
        this.error(`未在 ${helpDirectoryPath} 找到帮助文章，终止构建以免发布空的帮助中心。`);
      }
      const outputDirectoryPath = outputOptions.dir || path.resolve(config.root, "dist");
      for (const article of articleList) {
        const articleOutputPath = path.join(outputDirectoryPath, "help", `${article.slug}.md`);
        fs.mkdirSync(path.dirname(articleOutputPath), { recursive: true });
        fs.writeFileSync(articleOutputPath, article.markdownSourceText);
      }
      fs.writeFileSync(path.join(outputDirectoryPath, "llms.txt"), buildLlmsIndex(articleList, config.base, options));
      fs.writeFileSync(
        path.join(outputDirectoryPath, "llms-full.txt"),
        articleList
          .map((article) => `<!-- source: ${config!.base}help/${article.slug}.md -->\n${article.markdownSourceText.trim()}`)
          .join("\n\n---\n\n") + "\n",
      );
    },
  };
}
