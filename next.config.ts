import type { NextConfig } from "next";

// In development the Python API runs separately (npm run dev:api on port 8000); on Vercel, vercel.json routes /api/*.
const nextConfig: NextConfig = {
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }]
      : [];
  },
  images: { unoptimized: true },
  devIndicators: false,
};
export default nextConfig;
