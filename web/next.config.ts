import type { NextConfig } from "next";

const quorumApiBaseUrl =
  process.env.QUORUM_API_BASE_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/quorum/:path*",
        destination: `${quorumApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
