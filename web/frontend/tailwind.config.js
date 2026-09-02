/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0c1222',
        'ink-soft': '#243044',
        body: '#5a6578',
        muted: '#8a93a3',
        canvas: '#ffffff',
        fog: '#eef1f5',
        line: '#d5dbe5',
        'line-strong': '#b8c0ce',
        // Primary accent (was moss): cool cobalt, not teal-on-cream
        moss: '#1f5eff',
        'moss-deep': '#0f3fcc',
        'moss-soft': '#e8efff',
        // Secondary mark (was copper): amber for pattern tags only
        copper: '#b45309',
        'copper-soft': '#fff4e6',
        rail: '#121826',
        'rail-line': '#2a3348',
        'rail-mute': '#9aa3b5',
        error: '#c62828',
        'error-soft': '#fdecea',
        'error-line': '#f0c2c0',
        'code-ink': '#0f172a'
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"IBM Plex Serif"', 'Georgia', 'serif']
      },
      boxShadow: {
        soft: '0 1px 0 rgba(12, 18, 34, 0.04), 0 8px 20px rgba(12, 18, 34, 0.05)',
        lift: '0 2px 4px rgba(12, 18, 34, 0.05), 0 14px 32px rgba(12, 18, 34, 0.08)'
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' }
        }
      },
      animation: {
        'fade-up': 'fade-up 360ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in': 'fade-in 240ms ease-out both'
      }
    }
  },
  plugins: []
}
