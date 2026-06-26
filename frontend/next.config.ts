import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // React Compiler is disabled: in this stack (Next 16 + React 19 + Zustand 5)
  // its v1.0 auto-memoization stopped components from re-rendering when the
  // Zustand store changed. We don't need it for this project.
  reactCompiler: false,
};

export default nextConfig;