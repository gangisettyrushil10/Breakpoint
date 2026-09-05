import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { ProfileProvider } from "@/components/ProfileProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "BreakPoint — Financial resilience under compound emergencies",
  description:
    "How many bad things can happen before your finances break? A deterministic stress test for short- and medium-term financial resilience.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-bg text-ink">
        {/* Above the router so / and /chat share one profile and one transcript.
            This file stays a server component — the directive is in the providers.
            Auth wraps profile because which store backs the profile depends on
            who is signed in. */}
        <AuthProvider>
          <ProfileProvider>{children}</ProfileProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
