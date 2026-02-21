import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hashed Control Plane",
  description: "AI Agent Governance Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
