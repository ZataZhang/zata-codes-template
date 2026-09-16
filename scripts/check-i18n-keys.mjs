#!/usr/bin/env node
/**
 * 校验两个前端的 en/zh 文案文件 key 一一对应、无缺 key。
 *
 * 覆盖的文案文件对（相对仓库根）：
 *   - frontend-public/messages/{en,zh}.json   （next-intl，SSR cookie 模式）
 *   - frontend-admin/src/locales/{en,zh}.json （react-i18next，客户端模式）
 *
 * 退出码：0 = 全部对齐；1 = 存在缺失/多余 key 或文件读取失败。
 *
 * 用法：
 *   node scripts/check-i18n-keys.mjs                 # 校验内置的全部文案对
 *   node scripts/check-i18n-keys.mjs <en> <zh> ...   # 只校验显式给出的 en/zh 对
 *
 * 该脚本是 PRD §7.2 / FR-5 的缺 key 校验入口，同时被
 * `just check-i18n-keys`、`hooks/check_i18n_keys.py` 与 CI frontend-build job 调用。
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
/** 仓库根目录（本脚本位于 <root>/scripts/ 下）。 */
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..");

/** 默认校验的文案文件对，路径相对仓库根。 */
const DEFAULT_LOCALE_PAIRS = [
  ["frontend-public/messages/en.json", "frontend-public/messages/zh.json"],
  ["frontend-admin/src/locales/en.json", "frontend-admin/src/locales/zh.json"],
];

/**
 * 把嵌套的文案对象拍平成「点号分隔的叶子 key」集合。
 *
 * @param {unknown} node 当前递归到的节点。
 * @param {string} prefix 已累积的点号路径前缀。
 * @param {Set<string>} collected 收集叶子 key 的集合（原地修改）。
 * @returns {Set<string>} 与 collected 相同的集合。
 */
function collectLeafKeys(node, prefix, collected) {
  if (node === null || typeof node !== "object" || Array.isArray(node)) {
    // 叶子（含 null / 数组 / 标量）：null 与数组同样视为叶子，避免把
    // 数组下标当成 key 参与对齐比较。
    collected.add(prefix);
    return collected;
  }

  for (const [childKey, childValue] of Object.entries(node)) {
    const childPath = prefix === "" ? childKey : `${prefix}.${childKey}`;
    collectLeafKeys(childValue, childPath, collected);
  }
  return collected;
}

/**
 * 读取并拍平一份文案文件。
 *
 * @param {string} relativePath 相对仓库根的文案文件路径。
 * @returns {{ keys: Set<string> } | { error: string }} 成功时返回叶子 key 集合。
 */
function loadLocaleKeys(relativePath) {
  const absolutePath = path.resolve(REPO_ROOT, relativePath);
  let rawContent;
  try {
    rawContent = readFileSync(absolutePath, "utf8");
  } catch (readError) {
    return { error: `无法读取文案文件 ${relativePath}：${readError.message}` };
  }

  let parsed;
  try {
    parsed = JSON.parse(rawContent);
  } catch (parseError) {
    return { error: `文案文件 ${relativePath} 不是合法 JSON：${parseError.message}` };
  }

  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { error: `文案文件 ${relativePath} 顶层必须是对象。` };
  }

  return { keys: collectLeafKeys(parsed, "", new Set()) };
}

/**
 * 求集合差集 a - b，返回按字典序排序的数组，保证输出稳定可 diff。
 *
 * @param {Set<string>} a 被减集合。
 * @param {Set<string>} b 减数集合。
 * @returns {string[]} a 中存在而 b 中不存在的 key。
 */
function difference(a, b) {
  return [...a].filter((key) => !b.has(key)).sort();
}

/**
 * 校验一对 en/zh 文案文件。
 *
 * @param {string} enPath 英文文案文件路径（相对仓库根）。
 * @param {string} zhPath 中文文案文件路径（相对仓库根）。
 * @returns {{ failed: boolean, lines: string[] }} 该对的校验结果。
 */
function checkPair(enPath, zhPath) {
  const enResult = loadLocaleKeys(enPath);
  const zhResult = loadLocaleKeys(zhPath);

  if (enResult.error || zhResult.error) {
    return { failed: true, lines: [enResult.error ?? zhResult.error] };
  }

  const missingInZh = difference(enResult.keys, zhResult.keys);
  const extraInZh = difference(zhResult.keys, enResult.keys);

  const lines = [
    `── ${enPath} ↔ ${zhPath}`,
    `   en 叶子 key 数：${enResult.keys.size}，zh 叶子 key 数：${zhResult.keys.size}`,
    `   missing-in-zh: [${missingInZh.join(", ")}]`,
    `   extra-in-zh:   [${extraInZh.join(", ")}]`,
  ];

  return { failed: missingInZh.length > 0 || extraInZh.length > 0, lines };
}

/**
 * 解析命令行参数，得到待校验的 en/zh 文件对。
 *
 * @param {string[]} argv 进程参数（已去掉 node 与脚本路径）。
 * @returns {string[][]} 文案文件对列表。
 * @throws {Error} 参数个数不是偶数时抛出。
 */
function resolveLocalePairs(argv) {
  if (argv.length === 0) {
    return DEFAULT_LOCALE_PAIRS;
  }
  if (argv.length % 2 !== 0) {
    throw new Error(
      "参数必须是成对的 <en.json> <zh.json>；也可不传参数以校验内置的全部文案对。",
    );
  }
  const pairs = [];
  for (let index = 0; index < argv.length; index += 2) {
    pairs.push([argv[index], argv[index + 1]]);
  }
  return pairs;
}

/**
 * 脚本入口。
 *
 * @returns {number} 进程退出码：0 表示全部对齐，1 表示存在缺 key 或读取失败。
 */
function main() {
  let localePairs;
  try {
    localePairs = resolveLocalePairs(process.argv.slice(2));
  } catch (argumentError) {
    console.error(`[ERROR] ${argumentError.message}`);
    return 1;
  }

  console.log(`🔍 校验 en/zh 文案 key 对齐（仓库根：${REPO_ROOT}）`);

  let hasFailure = false;
  for (const [enPath, zhPath] of localePairs) {
    const { failed, lines } = checkPair(enPath, zhPath);
    for (const line of lines) {
      console.log(line);
    }
    if (failed) {
      hasFailure = true;
    }
  }

  if (hasFailure) {
    console.error(
      "\n[ERROR] en/zh 文案 key 未对齐：请按上面的 missing-in-zh / extra-in-zh 列表补齐或删除对应 key。",
    );
    return 1;
  }

  console.log("\n✅ 全部文案文件 en/zh key 一一对应。");
  return 0;
}

process.exit(main());
