import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/**
 * 阻止公开 BFF 将私有后端指标端点代理给浏览器。
 * @param request - 当前 Next.js 请求。
 * @returns 指标路径返回 404，其余请求继续进入 Next.js 路由。
 */
export function proxy(request: NextRequest): NextResponse | undefined {
  if (
    request.nextUrl.pathname === "/api/metrics" ||
    request.nextUrl.pathname.startsWith("/api/metrics/")
  ) {
    return new NextResponse(null, { status: 404 })
  }

  return NextResponse.next()
}

export const config = {
  matcher: "/api/metrics/:path*",
}
