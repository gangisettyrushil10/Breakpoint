import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: {
    // Mirrors the "@/*" -> "./*" mapping in tsconfig.json. Without it the test
    // run resolves imports differently from the build, which is the kind of
    // divergence that makes a green suite meaningless.
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    include: ["tests/**/*.test.ts"],
  },
});
