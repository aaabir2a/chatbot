import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import dts from "vite-plugin-dts";

// npm library build: ESM + CJS, React kept external (peer dependency).
export default defineConfig({
  plugins: [react(), dts({ rollupTypes: true, include: ["src"] })],
  build: {
    lib: {
      entry: "src/index.ts",
      name: "RagChatWidget",
      formats: ["es", "cjs"],
      fileName: (format) =>
        format === "es" ? "rag-chat-widget.js" : "rag-chat-widget.cjs",
    },
    rollupOptions: {
      external: ["react", "react-dom", "react/jsx-runtime"],
      output: {
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
          "react/jsx-runtime": "jsxRuntime",
        },
      },
    },
    emptyOutDir: true,
  },
});
