/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1c1712',
        'ink-soft': '#3a3226',
        body: '#6f6656',
        muted: '#9c9484',
        canvas: '#fffefb',
        moss: '#44624a',
        'moss-deep': '#324a37',
        'moss-soft': '#e3ebe0',
        copper: '#a65f35',
        'copper-soft': '#f3e6da',
        fog: '#f2efe6',
        line: '#ddd5c2',
        'line-strong': '#c4b9a1',
        error: '#b3261e',
        'error-soft': '#fbeae7',
        'error-line': '#e7c4bc',
        'code-ink': '#201a12'
      },
      fontFamily: {
        serif: ['"Source Serif 4"', 'Georgia', '"Times New Roman"', 'serif']
      }
    }
  },
  plugins: []
}
