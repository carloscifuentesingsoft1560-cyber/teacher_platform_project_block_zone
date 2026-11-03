import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const raiz = fileURLToPath(new URL('../', import.meta.url));
export default defineConfig(({ mode }) => {
  const entorno = loadEnv(mode, raiz, '');
  return {
    plugins: [react()],
    // Solo VITE_* se expone al navegador. El destino permanece en Node.
    server: {
      host: '127.0.0.1', port: 5173, strictPort: true,
      proxy: {
        '/api': { target: entorno.BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/pruebas/preparacion.js'],
      clearMocks: true,
    },
  };
});
