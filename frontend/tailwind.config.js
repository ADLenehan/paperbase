/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        coral: {
          50: '#fef5f4',
          100: '#fde9e7',
          200: '#fbd6d2',
          300: '#f8b8b0',
          400: '#f38e82',
          500: '#e97563',  // Main coral
          600: '#d55947',
          700: '#b3443a',
          800: '#943d35',
          900: '#7c3732',
        },
        orange: {
          50: '#fef7ed',
          100: '#fdecd4',
          200: '#fad7a8',
          300: '#f7bb71',
          400: '#f39438',  // Main orange
          500: '#f07818',
          600: '#e1590e',
          700: '#bb420e',
          800: '#953513',
          900: '#792e13',
        },
        yellow: {
          50: '#fefce8',
          100: '#fef9c3',
          200: '#fef08a',
          300: '#fde047',
          400: '#facc15',  // Main yellow
          500: '#eab308',
          600: '#ca8a04',
          700: '#a16207',
          800: '#854d0e',
          900: '#713f12',
        },
        mint: {
          50: '#f0fdf5',
          100: '#dcfce8',
          200: '#bbf7d1',
          300: '#86efac',
          400: '#4ade80',  // Main mint
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        sky: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',  // Main sky blue
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        periwinkle: {
          50: '#f5f7ff',
          100: '#ebf0ff',
          200: '#dce3ff',
          300: '#beccff',
          400: '#99aaff',  // Main periwinkle
          500: '#7488ff',
          600: '#5560ff',
          700: '#4348e8',
          800: '#373dbb',
          900: '#313794',
        },
        // Alias primary to coral for common usage
        primary: {
          50: '#fef5f4',
          100: '#fde9e7',
          200: '#fbd6d2',
          300: '#f8b8b0',
          400: '#f38e82',
          500: '#e97563',  // Main coral
          600: '#d55947',
          700: '#b3443a',
          800: '#943d35',
          900: '#7c3732',
        },
      },
    },
  },
  plugins: [],
}
