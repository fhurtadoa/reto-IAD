import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import "katex/dist/katex.min.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "OptiCompromise — Programación de Compromiso Multiobjetivo | UNAL",
  description: "Herramienta interactiva para resolución de problemas multiobjetivo continuos por programación de compromiso (L1, L2, L_infinito). Facultad de Minas - Universidad Nacional de Colombia.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[#F3F4F8] dark:bg-[#111524] text-slate-900 dark:text-slate-100`}>
        {children}
      </body>
    </html>
  );
}
