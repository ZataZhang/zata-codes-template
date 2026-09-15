import type { NextConfig } from "next"
import createNextIntlPlugin from "next-intl/plugin"

// 把 i18n/request.ts 注册为 next-intl 的请求配置入口：插件在服务端渲染时
// 调用它解析 locale 与文案，客户端则由根布局注入的 Provider 提供。
const withNextIntl = createNextIntlPlugin("./i18n/request.ts")

const backendUrl =
  process.env.BACKEND_URL || process.env.API_BASE_URL || "http://localhost:8000"

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ]
  },
}

export default withNextIntl(nextConfig)
