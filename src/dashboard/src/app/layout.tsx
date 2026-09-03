import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

// Font stack theo docs/claude/design-system.md v3.1: Inter cho UI, IBM Plex Mono
// cho công thức/ID/timestamp — dấu ấn typographic của sản phẩm, không phải trang trí.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Threads AI Content — Dashboard",
  description: "Internal analytics dashboard for the 'thydilammuon' Threads channel.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${ibmPlexMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg-page text-text-primary">
        <Nav />
        {children}
      </body>
    </html>
  );
}
