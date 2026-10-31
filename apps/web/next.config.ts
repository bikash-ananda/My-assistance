import type { NextConfig } from "next";

const api = process.env.BIKASH_API_INTERNAL_URL || "http://127.0.0.1:8000";

const config: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: api + "/api/:path*" },
      { source: "/health/:path*", destination: api + "/health/:path*" }
    ];
  }
};

export default config;
