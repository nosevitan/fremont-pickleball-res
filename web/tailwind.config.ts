import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        pickle: {
          DEFAULT: "#66B333",
          dark: "#4A8526",
          light: "#7FCC4D",
        },
      },
    },
  },
  plugins: [],
};

export default config;
