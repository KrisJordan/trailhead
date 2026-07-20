import { defineConfig, loadEnv, type Plugin, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:1109'
const DEFAULT_STATIC_DIR = '../server/src/trailhead/static'

function backendProxy(target: string): Record<string, string | ProxyOptions> {
  const httpProxy: ProxyOptions = {
    target,
    // Preserve the browser-facing Host header. This lets Trailhead compare it
    // with the WebSocket Origin directly, including on custom loopback ports.
    changeOrigin: false,
  }

  return {
    '/api': httpProxy,
    '/docs': httpProxy,
    '/openapi.json': httpProxy,
    '/ws': {
      ...httpProxy,
      ws: true,
    },
  }
}

function preserveStaticPlaceholders(): Plugin {
  return {
    name: 'preserve-static-placeholders',
    apply: 'build',
    buildStart() {
      this.emitFile({ type: 'asset', fileName: '.gitkeep', source: '' })
      this.emitFile({ type: 'asset', fileName: 'assets/.gitkeep', source: '' })
    },
  }
}

// In development Vite replaces the Caddy reverse proxy that was used by the
// devcontainer. Production assets always go to the Python package's static tree
// so a stale environment variable can never empty an unrelated directory.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const proxy = backendProxy(env.TRAILHEAD_BACKEND_URL || DEFAULT_BACKEND_URL)

  return {
    plugins: [react(), preserveStaticPlaceholders()],
    server: {
      port: 1110,
      strictPort: true,
      proxy,
    },
    preview: {
      port: 1110,
      strictPort: true,
      proxy,
    },
    build: {
      outDir: DEFAULT_STATIC_DIR,
      emptyOutDir: true,
    },
  }
})
