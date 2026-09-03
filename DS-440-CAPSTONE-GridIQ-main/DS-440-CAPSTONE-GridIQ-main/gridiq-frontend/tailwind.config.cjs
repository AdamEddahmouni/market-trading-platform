/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        stadium: {
          night: "#0c1222",
          sky: "#1a2f4a",
          turf: "#1b5e3a",
          turfMuted: "#2f7d52",
          track: "#3d3530",
          line: "#f4f1e8",
          concrete: "#ece8de",
          gold: "#d4a817",
          goldSoft: "#f0d875",
        },
      },
      backgroundImage: {
        "stadium-field":
          "linear-gradient(165deg, #0c1222 0%, #152a45 38%, #1b5e3a 78%, #0f2918 100%)",
      },
      boxShadow: {
        panel: "0 8px 30px rgba(0,0,0,0.12)",
      },
    },
  },
  plugins: [],
};
