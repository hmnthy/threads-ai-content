import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

// Font stack theo docs/claude/design-system.md: Inter -> system-ui -> sans-serif
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Threads AI Content — Dashboard",
  description: "Internal analytics dashboard for the 'thydilammuon' Threads channel.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg-primary text-text-primary">
        <Nav />
        {children}
      </body>
    </html>
  );
}
