import { execFileSync } from "node:child_process";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

function getCommitHash(): string {
  try {
    return execFileSync("git", ["rev-parse", "--short", "HEAD"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "dev";
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const buildOutDir = env.VITE_BUILD_OUT_DIR || "dist";

  return {
    base: "/app/",
    plugins: [
      react(),
      {
        name: "html-document-title",
        transformIndexHtml(html) {
          const title = env.VITE_APP_DOCUMENT_TITLE || "New Ridge Financial Browser App";
          return html.replace(/<title>.*?<\/title>/, `<title>${title}</title>`);
        },
      },
    ],
    build: {
      outDir: buildOutDir,
      emptyOutDir: true,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("node_modules")) {
              return undefined;
            }

            if (id.includes("recharts")) {
              return "charts";
            }

            if (id.includes("@tanstack")) {
              return "tanstack";
            }

            return "vendor";
          },
        },
      },
    },
    define: {
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? "0.0.0"),
      __BUILD_DATE__: JSON.stringify(new Date().toISOString()),
      __COMMIT_HASH__: JSON.stringify(process.env.GITHUB_SHA?.slice(0, 7) ?? getCommitHash()),
    },
    // NewRidgeFinancial browser API (HAL chat + auth) on :8096 during dev/preview.
    server: {
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8096",
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8096",
          changeOrigin: true,
        },
      },
    },
  };
});
