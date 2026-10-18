import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 서버: /api, /media 요청을 백엔드(uvicorn)로 넘긴다.
// 같은 origin으로 묶이므로 세션 쿠키가 그대로 동작하고 CORS 설정이 필요 없다.
const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": BACKEND,
      "/media": BACKEND,
    },
  },
});
