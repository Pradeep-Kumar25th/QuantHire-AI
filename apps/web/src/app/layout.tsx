import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "QuantHireAI - Agentic Hiring Platform",
  description:
    "Multi-agent, explainable, evidence-backed hiring — specialist AI swarm for enterprise recruiters.",
  openGraph: {
    title: "QuantHireAI - Agentic Hiring Platform",
  },
  icons: {
    icon: [
      { url: "/brand/quanthire-mark.png", sizes: "512x512", type: "image/png" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
    shortcut: "/brand/quanthire-mark.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
