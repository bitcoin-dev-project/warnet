import type { Config } from 'tailwindcss';

const config: Config = {
    content: ['./src/pages/**/*.{js,ts,jsx,tsx,mdx}', './src/components/**/*.{js,ts,jsx,tsx,mdx}', './src/app/**/*.{js,ts,jsx,tsx,mdx}'],
    theme: {
        extend: {
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
            },
            colors: {
                'custom-gray': '#C4C4C4',
                'custom-purple': '#FF02A9',
            },
            fontSize: {
                'custom-logo': '64px',
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
};
export default config;
