import { apiGet } from "./client"
import type { ToolDefinition } from "@/lib/types/tool"

export async function listTools(): Promise<ToolDefinition[]> {
  return apiGet<ToolDefinition[]>("/tools")
}
