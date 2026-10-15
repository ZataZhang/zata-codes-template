import fs from "node:fs";
import path from "node:path";

import { parse as parseYaml } from "yaml";
import type { Plugin, ResolvedConfig } from "vite";

/** 帮助文章 frontmatter 中供静态索引使用的字段。 */
type HelpStaticArticle = {
  slug: string;
  category: string;
  order: number;
  title: string;
  summary: string;
  markdownSourceText: string;
};

const FRONTMATTER_PATTERN = /^---\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/;
const HELP_ARTICLE_DIRECTORY_LIST = ["product", "api"];

function listMarkdownPath(directoryPath: string): string[] {
  if (!fs.existsSync(directoryPath)) {
    return [];
  }
  return fs.readdirSync(directoryPath, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md") && entry.name !== "index.md")
    .map((entry) => path.join(entry.parentPath, entry.name));
}

function readHelpStaticArticleList(helpDirectoryPath: string): HelpStaticArticle[] {
  const articleList = HELP_ARTICLE_DIRECTORY_LIST
    .flatMap((directoryName) => listMarkdownPath(path.join(helpDirectoryPath, directoryName)))
    .map((markdownPath) => {
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
        throw new Error(`帮助文章 ${markdownPath} 缺少发布静态文件所需的 frontmatter 字段。`);
      }
      return { ...metadata, markdownSourceText } as HelpStaticArticle;
    });
  return articleList.sort((articleA, articleB) => articleA.order - articleB.order);
}

function buildLlmsIndex(articleList: HelpStaticArticle[], basePath: string): string {
  const lineList = [
    "# F-Sense 单证识别帮助中心",
    "",
    "> F-Sense 单证识别的产品使用与 API 接入文档。每篇文章都有可直接读取的 Markdown 原文；"
      + "接口的机器可读契约见 /api/openapi.json。",
    "",
  ];
  for (const categoryName of [...new Set(articleList.map((article) => article.category))]) {
    lineList.push(`## ${categoryName}`, "");
    for (const article of articleList.filter((item) => item.category === categoryName)) {
      lineList.push(`- [${article.title}](${basePath}help/${article.slug}.md): ${article.summary}`);
    }
    lineList.push("");
  }
  lineList.push(
    "## 机器可读契约",
    "",
    "- [OpenAPI 契约](/api/openapi.json): 全部 HTTP 接口的方法、路径与参数。",
    "- [全部文章合订本](" + basePath + "llms-full.txt): 上述全部文章的 Markdown 原文，适合一次读取。",
    "",
  );
  return lineList.join("\n");
}

/**
 * 构建时把 docs/help 的 Markdown 原文发布为静态文件，便于不执行 JS 的 agent 读取。
 *
 * 产物：`help/<slug>.md`、`llms.txt`、`llms-full.txt`。正文来源与产品内帮助中心一致，
 * 不在此处另存副本。
 */
export function helpStaticPlugin(): Plugin {
  let config: ResolvedConfig | undefined;
  return {
    name: "help-static",
    apply: "build",
    configResolved(resolvedConfig) {
      config = resolvedConfig;
    },
    writeBundle(options) {
      if (!config) {
        return;
      }
      const helpDirectoryPath = path.resolve(config.root, "../../docs/help");
      const articleList = readHelpStaticArticleList(helpDirectoryPath);
      if (articleList.length === 0) {
        // 与帮助中心加载器保持一致：没有文章源时不发布空索引。
        this.warn(`未在 ${helpDirectoryPath} 找到帮助文章，跳过 llms.txt 与 Markdown 发布。`);
        return;
      }
      const outputDirectoryPath = options.dir || path.resolve(config.root, "dist");
      for (const article of articleList) {
        const articleOutputPath = path.join(outputDirectoryPath, "help", `${article.slug}.md`);
        fs.mkdirSync(path.dirname(articleOutputPath), { recursive: true });
        fs.writeFileSync(articleOutputPath, article.markdownSourceText);
      }
      fs.writeFileSync(
        path.join(outputDirectoryPath, "llms.txt"),
        buildLlmsIndex(articleList, config.base),
      );
      fs.writeFileSync(
        path.join(outputDirectoryPath, "llms-full.txt"),
        articleList
          .map((article) => `<!-- source: ${config!.base}help/${article.slug}.md -->\n${article.markdownSourceText.trim()}`)
          .join("\n\n---\n\n") + "\n",
      );
    },
  };
}
