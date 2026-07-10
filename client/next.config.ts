import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  assetPrefix: '/izatabi',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8088/api/:path*',
      },
    ];
  },
};

export default nextConfig;
