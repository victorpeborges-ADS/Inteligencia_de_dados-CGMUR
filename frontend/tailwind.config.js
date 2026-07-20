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
          emerald: "#10b981",  // vegetation/cooling
          sky: "#0ea5e9",      // flooding/water
          amber: "#f59e0b",    // warnings
          rose: "#f43f5e",     // landslides/hazards
          indigo: "#6366f1"    // urban network/AI
        }
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
}
