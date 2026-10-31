import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bikash AI",
  description: "Private workspace for your AI assistant",
  applicationName: "Bikash AI",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Bikash AI", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/icon.svg" }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
