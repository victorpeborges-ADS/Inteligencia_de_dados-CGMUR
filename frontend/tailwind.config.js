/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#09090b", // zinc-950
        card: "#18181b",       // zinc-900
        border: "#27272a",     // zinc-800
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
