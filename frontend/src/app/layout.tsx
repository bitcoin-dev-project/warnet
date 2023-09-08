import './globals.css'
import type { Metadata } from 'next'
import { Inter, IBM_Plex_Sans } from 'next/font/google'

const inter = Inter({ subsets: ['latin'], variable: "--font-inter" })
const ibm = IBM_Plex_Sans({ 
  subsets: ['latin'],
  weight: ["100", "200", "300", "400", "500", "600", "700"],
  variable: "--font-ibm",
  display: "swap",
  style: ["normal"],
})

export const metadata: Metadata = {
  title: 'Warnet',
  description: 'Warnet',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${ibm.variable} font-ibm`}>{children}</body>
    </html>
  )
}
