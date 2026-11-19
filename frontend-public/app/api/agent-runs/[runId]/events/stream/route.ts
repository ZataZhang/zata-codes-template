import { backendBaseUrl } from "@/lib/backend-url"
import type { NextRequest } from "next/server"

export const dynamic = "force-dynamic"
export const revalidate = 0

/** 将成员 Agent Run 的 SSE 响应体直接流式转发到后端。 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ runId: string }> },
): Promise<Response> {
  const { runId } = await context.params
  const upstreamUrl = new URL(
    `/agent-runs/${encodeURIComponent(runId)}/events/stream`,
    backendBaseUrl,
  )
  upstreamUrl.search = request.nextUrl.search

  const upstreamRequestHeaders = new Headers()
  for (const headerName of ["accept", "authorization", "cookie", "last-event-id"]) {
    const headerValue = request.headers.get(headerName)
    if (headerValue) upstreamRequestHeaders.set(headerName, headerValue)
  }

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      headers: upstreamRequestHeaders,
      cache: "no-store",
      signal: request.signal,
    })
    const responseHeaders = new Headers({
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    })
    const contentType = upstreamResponse.headers.get("content-type")
    if (contentType) responseHeaders.set("Content-Type", contentType)

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    })
  } catch {
    return Response.json(
      { detail: "Agent run event stream is unavailable" },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    )
  }
}
