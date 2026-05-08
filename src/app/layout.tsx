import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "FinAI - Accounting & Finance Assistant",
  description: "AI-Powered Accounting & Finance Assistant for analyzing financial documents, tax risks, and legislations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body className="min-h-full flex overflow-hidden bg-zinc-950 text-zinc-200">
        <Sidebar />
        <main className="flex-1 flex flex-col h-screen overflow-hidden p-4">
          {children}
        </main>
      </body>
    </html>
  );
}
