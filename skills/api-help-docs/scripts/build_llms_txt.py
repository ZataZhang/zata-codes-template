#!/usr/bin/env python3
"""把带 frontmatter 的帮助文章 Markdown 发布成静态 .md、llms.txt 与 llms-full.txt。

适用于没有前端构建步骤的纯后端项目；有 Vite 前端时用 assets/help-static.ts。
只依赖 PyYAML。正文不改写，产物与源 Markdown 逐字一致。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

FRONTMATTER_PATTERN = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)")
REQUIRED_FIELDS = ("slug", "category", "order", "title", "summary")


def read_article_list(docs_directory: Path, category_directory_list: list[str]) -> list[dict]:
    """读取文章 frontmatter 并按 order 排序；缺字段时直接报错，避免发布残缺索引。"""
    article_list: list[dict] = []
    for category_directory in category_directory_list:
        for markdown_path in sorted((docs_directory / category_directory).rglob("*.md")):
            if markdown_path.name == "index.md":
                continue
            source_text = markdown_path.read_text(encoding="utf-8")
            frontmatter_match = FRONTMATTER_PATTERN.match(source_text)
            metadata = yaml.safe_load(frontmatter_match.group(1)) if frontmatter_match else None
            if not isinstance(metadata, dict):
                raise SystemExit(f"{markdown_path}: 缺少 YAML frontmatter")
            missing_field_list = [name for name in REQUIRED_FIELDS if name not in metadata]
            if missing_field_list:
                raise SystemExit(f"{markdown_path}: frontmatter 缺少字段 {missing_field_list}")
            article_list.append({**metadata, "source_text": source_text})
    slug_list = [article["slug"] for article in article_list]
    duplicate_slug_list = sorted({slug for slug in slug_list if slug_list.count(slug) > 1})
    if duplicate_slug_list:
        raise SystemExit(f"slug 重复：{duplicate_slug_list}")
    return sorted(article_list, key=lambda article: article["order"])


def build_index(
    article_list: list[dict], title: str, description: str, base_path: str, openapi_url: str | None
) -> str:
    """生成 llms.txt：标题、摘要、每篇文章的 .md 链接，以及可选的 OpenAPI 地址。"""
    line_list = [f"# {title}", "", f"> {description}", ""]
    for category in dict.fromkeys(article["category"] for article in article_list):
        line_list += [f"## {category}", ""]
        line_list += [
            f"- [{article['title']}]({base_path}{article['slug']}.md): {article['summary']}"
            for article in article_list
            if article["category"] == category
        ]
        line_list.append("")
    line_list += ["## 机器可读契约", ""]
    if openapi_url:
        line_list.append(f"- [OpenAPI 契约]({openapi_url}): 全部 HTTP 接口的方法、路径与参数。")
    line_list += [
        f"- [全部文章合订本]({base_path.rsplit('/', 2)[0]}/llms-full.txt): 全部文章原文。",
        "",
    ]
    return "\n".join(line_list)


def main() -> int:
    """解析参数并写出静态文件。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, required=True, help="文章根目录，如 docs/help")
    parser.add_argument("--out-dir", type=Path, required=True, help="静态站点输出目录")
    parser.add_argument("--categories", default="product,api", help="逗号分隔的文章子目录")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--base-path", default="/help/", help="文章 URL 前缀，需以 / 结尾")
    parser.add_argument(
        "--openapi-url", default=None, help="OpenAPI JSON 的 URL，如 /api/openapi.json"
    )
    arguments = parser.parse_args()

    article_list = read_article_list(arguments.docs_dir, arguments.categories.split(","))
    if not article_list:
        print(f"未在 {arguments.docs_dir} 找到文章，未生成任何文件。", file=sys.stderr)
        return 1
    arguments.out_dir.mkdir(parents=True, exist_ok=True)
    for article in article_list:
        article_path = arguments.out_dir / f"{article['slug']}.md"
        article_path.parent.mkdir(parents=True, exist_ok=True)
        article_path.write_text(article["source_text"], encoding="utf-8")
    (arguments.out_dir / "llms.txt").write_text(
        build_index(
            article_list,
            arguments.title,
            arguments.description,
            arguments.base_path,
            arguments.openapi_url,
        ),
        encoding="utf-8",
    )
    full_article_block_list: list[str] = [
        f"<!-- source: {arguments.base_path}{article['slug']}.md -->\n"
        f"{article['source_text'].strip()}"
        for article in article_list
    ]
    (arguments.out_dir / "llms-full.txt").write_text(
        "\n\n---\n\n".join(full_article_block_list) + "\n",
        encoding="utf-8",
    )
    print(f"已发布 {len(article_list)} 篇文章到 {arguments.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
