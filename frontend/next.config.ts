import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Content-Security-Policy",
    // Next + MetaMask need unsafe-inline / unsafe-eval in practice.
    // connect-src covers the indexer API, Studionet RPC, and explorer.
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      [
        "connect-src 'self'",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://studio.genlayer.com",
        "https://explorer-studio.genlayer.com",
        "https://*.genlayer.com",
        "wss:",
        "https:",
        "chrome-extension:",
        "moz-extension:",
      ].join(" "),
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  // Studionet RPC is not a standard Ethereum endpoint; wallet writes go
  // through genlayer-js, not wagmi transports.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
