import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  webpack(config) {
    // supabase-js guards this process.version probe before executing it. The
    // Edge analyzer cannot prove the guard and emits a false-positive warning.
    config.ignoreWarnings = [
      ...(config.ignoreWarnings ?? []),
      {
        module: /@supabase[\\/]supabase-js[\\/]dist[\\/]index\.mjs/,
        message: /A Node\.js API is used \(process\.version/
      }
    ];
    // The generated route/catalog payload is large enough to trigger PackFile
    // serialization warnings. Memory cache keeps per-process reuse without the
    // noisy persistent serialization step in dev, E2E or production builds.
    config.cache = { type: "memory" };
    return config;
  }
};

export default nextConfig;
