import type { SupportedLocale } from "./constants";

/**
 * 把 `Accept-Language` 请求头归一化为受支持的 locale。
 *
 * 只按语言主标签匹配：`zh-*` 归到 `zh`、`en-*` 归到 `en`，其余（如 `fr-FR`）
 * 返回 null 交给调用方回退到默认 locale。按请求头中出现的顺序取第一个命中项，
 * 因此 `zh-CN,zh;q=0.9,en;q=0.8` 会得到 `zh`。
 *
 * @param header - 原始 `Accept-Language` 请求头内容。
 * @returns 命中的受支持 locale，无命中时返回 null。
 */
export function negotiateAcceptLanguage(
  header: string
): SupportedLocale | null {
  for (const rawEntry of header.split(",")) {
    const tagPart = rawEntry.split(";", 1)[0]?.trim().toLowerCase();
    if (!tagPart) continue;
    const primary = tagPart.split("-", 1)[0];
    if (primary === "zh") return "zh";
    if (primary === "en") return "en";
  }
  return null;
}
