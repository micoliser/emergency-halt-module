import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Studionet RPC is not a standard Ethereum endpoint; wallet writes go
  // through genlayer-js, not wagmi transports.
};

export default nextConfig;
