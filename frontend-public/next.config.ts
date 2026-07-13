import type { NextConfig } from "next"

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

export default nextConfig
