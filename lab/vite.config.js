import { defineConfig } from 'vite';

export default defineConfig({
  publicDir: 'public',
  build: {
    outDir: '../site/lab',
    emptyOutDir: true,
  },
  server: {
    open: true,
  },
});
