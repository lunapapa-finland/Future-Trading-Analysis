import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Future Trading Analysis",
  description: "Modern web UI for futures trading analytics"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-slate-100">
        <Providers>
          <div className="min-h-screen bg-gradient-to-b from-background via-surface to-background">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
