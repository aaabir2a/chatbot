import { defineConfig } from "vite";

// Script-embed build: single self-contained IIFE (no React, no externals).
// Output: dist/widget.js — drop into any <script> tag.
export default defineConfig({
  build: {
    lib: {
      entry: "src/embed.ts",
      name: "RagChatBundle",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
    emptyOutDir: false, // keep the lib build output
    minify: "esbuild",
  },
});
