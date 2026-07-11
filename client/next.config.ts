import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  basePath: '/izatabi',
  // @ts-ignore
  turbopack: {
    root: path.join(__dirname),
  },
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
