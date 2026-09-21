import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [{ source: "/videos/upload", destination: "/videos", permanent: false }];
  },
};

export default nextConfig;
