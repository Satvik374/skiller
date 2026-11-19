import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  // The preview tunnel's hostname is supplied per environment, never committed:
  //   PREVIEW_HOST=xxx.style.dev npm run dev
  server: {
    host: "0.0.0.0",
    port: 3003,
    allowedHosts: process.env.PREVIEW_HOST ? [process.env.PREVIEW_HOST] : [],
  },
  build: { outDir: "dist", assetsInlineLimit: 0 },
});
