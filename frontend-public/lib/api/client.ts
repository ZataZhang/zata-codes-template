import axios from "axios"

export const apiClient = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
})

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message)
    this.name = "ApiRequestError"
  }
}

export async function apiGet<T>(url: string): Promise<T> {
  try {
    const response = await apiClient.get<T>(url)
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail
      throw new ApiRequestError(
        typeof detail === "string" ? detail : error.message,
        error.response?.status
      )
    }
    throw error
  }
}

export async function apiPost<T>(url: string, data: unknown): Promise<T> {
  try {
    const response = await apiClient.post<T>(url, data)
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail
      throw new ApiRequestError(
        typeof detail === "string" ? detail : error.message,
        error.response?.status
      )
    }
    throw error
  }
}
