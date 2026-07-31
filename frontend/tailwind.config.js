/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/design-system/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--sinidu-bg)",
        card: "var(--sinidu-card)",
        border: "var(--sinidu-border)",
        foreground: "var(--sinidu-fg)",
        accent: {
          emerald: "#10b981",
          sky: "#0ea5e9",
          amber: "#f59e0b",
          rose: "#f43f5e",
          teal: "#0d9488",
          indigo: "#6366f1",
        },
      },
      fontFamily: {
        sans: ['"Source Sans 3"', "Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
