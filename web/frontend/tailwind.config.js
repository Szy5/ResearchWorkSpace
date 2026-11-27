/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#34372f',
        'ink-soft': '#4b5045',
        body: '#6b7065',
        muted: '#7d8275',
        canvas: '#fffefa',
        fog: '#f5f5ef',
        line: '#e3e5db',
        'line-strong': '#c4c9ba',
        // Restrained sage accent.
        moss: '#53664c',
        'moss-deep': '#3d5038',
        'moss-soft': '#edf1e7',
        // Amber for uncertainty and attention.
        copper: '#936a32',
        'copper-soft': '#faf3e5',
        rail: '#f2f3ec',
        'rail-line': '#e0e3d7',
        'rail-mute': '#7b8270',
        error: '#c62828',
        'error-soft': '#fdecea',
        'error-line': '#f0c2c0',
        'code-ink': '#30352c'
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"IBM Plex Serif"', 'Georgia', 'serif']
      },
      boxShadow: {
        soft: '0 1px 2px rgba(40, 48, 32, 0.025)',
        lift: '0 10px 35px rgba(40, 48, 32, 0.09)'
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
