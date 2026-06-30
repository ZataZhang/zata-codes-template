import axios from "axios"

/** Axios instance for the public frontend API with credentials and 401 handling. */
export const apiClient = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      if (typeof window !== "undefined") {
        window.location.href = "/login"
      }
    }
    return Promise.reject(error)
  }
)

/** Error thrown for API requests with an optional HTTP status code. */
export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message)
    this.name = "ApiRequestError"
  }
}

/** Send a GET request and return the typed response data. */
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

/** Send a POST request with a JSON body and return the typed response data. */
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

/** Send a PUT request with a JSON body and return the typed response data. */
export async function apiPut<T>(url: string, data: unknown): Promise<T> {
  try {
    const response = await apiClient.put<T>(url, data)
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

/** Send a DELETE request and throw on failure. */
export async function apiDelete(url: string): Promise<void> {
  try {
    await apiClient.delete(url)
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
