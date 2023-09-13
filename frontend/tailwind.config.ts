import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        inter: ['var(--font-inter)'],
        ibm: ['var(--font-ibm)'],
      },
      fontSize: {
        'custom-logo': '64px',
      },
      colors: {
        "brand": {
          "purple": "#FF02A9",
          "gray-dark": "#262626",
          "gray-medium": "#393939",
          "gray-light": "#6F6F6F",
          "text-dark": "#C6C6C6",
          "text-light": "#F4F4F4"
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':
          'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
      backgroundColor: {
        'primary-transparent-black': 'rgba(0, 0, 0, 0.75)',
        'secondary-transparent-black': 'rgba(0, 0, 0, 0.35)',
        'gradient-dark-shade': 'rgba(77, 67, 76, 0.3)',
        'gradient-light-shade': 'rgba(77, 67, 76, 0.15)',
      },
      height: {
        'gradient-height': '700px',
      },
      width: {
        'gradient-width': '1300px',
      },
    },
  },
  plugins: [],
}
export default config
