import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The app is served from the same origin as the API in production, so it calls
// relative paths like /api/v1/analyses. In development the dev server proxies
// those to the API so the same relative paths work with no CORS involved.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8001'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      // shadcn components are written against the '@/' alias.
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      rollupOptions: {
        output: {
          /*
           * React and the router are the half of the bundle that does not
           * change when this app does. Splitting them out means a deploy that
           * touches a view leaves the framework chunk cached rather than
           * re-downloading it, and the entry chunk shrinks to app code.
           */
          manualChunks: {
            react: ['react', 'react-dom', 'react-dom/client'],
            router: ['react-router-dom'],
          },
        },
      },
    },
  }
})
