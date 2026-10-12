import type { Metadata, Viewport } from "next";
import { Big_Shoulders, Hanken_Grotesk } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/ui";
import { Shell } from "@/components/Shell";

// Big Shoulders Display is published on Google Fonts as the "Big Shoulders" family (display optical size).
const display = Big_Shoulders({ subsets: ["latin"], variable: "--font-display", weight: ["600", "800"] });
const text = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-text" });

export const metadata: Metadata = { title: "Match Day Optimizer", description: "Fantasy cricket teams you can defend, built for Dream11." };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#16213A" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable}`}>
      <body className="font-sans text-s16 antialiased">
        <Providers><Shell>{children}</Shell></Providers>
      </body>
    </html>
  );
}
