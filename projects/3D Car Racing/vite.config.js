import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    // The exact preview hostname is injected per VM; never a blanket allowlist.
    allowedHosts: (process.env.PREVIEW_HOST || '').split(',').filter(Boolean),
  },
  build: {
    target: 'esnext',
    chunkSizeWarningLimit: 2000,
  },
});
