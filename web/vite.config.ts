/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

/**
 * Plugin that prevents Vite from doing a full page reload when the
 * HMR WebSocket disconnects. Instead it silently reconnects.
 */
function noReloadOnDisconnect() {
  return {
    name: "no-reload-on-disconnect",
    transformIndexHtml(html: string) {
      // Inject a script BEFORE Vite's client that overrides location.reload
      // to no-op when triggered by the HMR disconnect handler.
      return html.replace(
        "</head>",
        `<script>
          (function() {
            var origReload = location.reload.bind(location);
            var blocked = false;
            // Listen for Vite's "server connection lost" console message
            var origLog = console.log;
            console.log = function() {
              var msg = Array.prototype.join.call(arguments, ' ');
              if (msg.indexOf('server connection lost') !== -1) {
                blocked = true;
                setTimeout(function() { blocked = false; }, 5000);
              }
              return origLog.apply(console, arguments);
            };
            Object.defineProperty(location, 'reload', {
              value: function() {
                if (blocked) {
                  console.log('[codehive] Suppressed HMR disconnect reload');
                  return;
                }
                return origReload();
              },
              writable: true,
              configurable: true
            });
          })();
        </script></head>`,
      );
    },
  };
}

export default defineConfig({
  plugins: [noReloadOnDisconnect(), react()],
  server: {
    hmr: {
      overlay: false,
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "index.html"),
        "service-worker": path.resolve(__dirname, "src/service-worker.ts"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "service-worker") {
            return "service-worker.js";
          }
          return "assets/[name]-[hash].js";
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    exclude: ["e2e/**", "node_modules/**"],
  },
});
