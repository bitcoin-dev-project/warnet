import './globals.css';
import type { Metadata } from 'next';
import { Inter, IBM_Plex_Mono } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });
const ibm_plex_mono = IBM_Plex_Mono({
    subsets: ['latin'],
    display: 'swap',
    weight: ['400', '700', '500'],
});

export const metadata: Metadata = {
    title: 'Warnet',
    description: 'Warnet',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang='en' className={ibm_plex_mono.className}>
            <body>{children}</body>
        </html>
    );
}
