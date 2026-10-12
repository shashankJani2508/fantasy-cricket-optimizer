import type { Metadata, Viewport } from "next";
import { Outfit, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/ui";
import { Shell } from "@/components/Shell";

const display = Outfit({ subsets: ["latin"], variable: "--font-display", weight: ["500", "600", "700", "800"] });
const text = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-text", weight: ["400", "500", "600"] });

export const metadata: Metadata = { title: "Match Day", description: "Fantasy cricket teams you can defend, built for Dream11." };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0A0B10" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable}`}>
      <body className="font-sans text-s16 text-ink antialiased">
        <Providers><Shell>{children}</Shell></Providers>
      </body>
    </html>
  );
}
