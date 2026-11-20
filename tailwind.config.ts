import type { Config } from "tailwindcss";
const config: Config = { content: ["./app/**/*.{ts,tsx}"], theme: { extend: { colors: { ink: "#09090f", panel: "#12121d", violet: "#9b87f5" } } }, plugins: [] };
export default config;
