import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Suspense } from "react";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-geist-sans" });

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: "ORBIS - Yapay Zeka Finans Asistanı",
  description: "ORBIS finansal belgeleri, vergi risklerini ve mevzuatı analiz eden yapay zeka destekli muhasebe ve finans asistanıdır.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" className={`${inter.variable} h-full antialiased dark overscroll-y-auto`}>
      <body className="h-full flex overflow-x-hidden bg-zinc-950 text-zinc-200">
        <Suspense>
          <Sidebar />
        </Suspense>
        <main className="flex-1 flex flex-col h-full min-h-0 min-w-0">
          {children}
        </main>
      </body>
    </html>
  );
}
