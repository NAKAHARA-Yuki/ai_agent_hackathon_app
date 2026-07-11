import type { Metadata } from "next";
import { Outfit, Inter } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "いざ旅 - AI旅行スタイル診断＆プランナー",
  description: "AIによる精密なパーソナライズ旅行スタイル診断と、AIエージェントによる旅程の自動提案＆調整プランナー",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ja"
      className={`${outfit.variable} ${inter.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[#f5f7fa]">
        <div className="mobile-container flex flex-col min-h-screen">
          {children}
        </div>
      </body>
    </html>
  );
}
