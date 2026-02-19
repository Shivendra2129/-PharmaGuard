import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PharmaGuard – Pharmacogenomic Risk Prediction",
  description:
    "RIFT 2026 Hackathon | AI-powered pharmacogenomic risk analysis using CPIC guidelines. Upload VCF files and get drug-specific safety predictions with explainable AI.",
  keywords: ["pharmacogenomics", "VCF", "CPIC", "drug safety", "AI", "genomics"],
  openGraph: {
    title: "PharmaGuard – Pharmacogenomic Risk Prediction",
    description: "AI-powered pharmacogenomic risk prediction system for precision medicine",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased bg-gray-950 text-gray-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
