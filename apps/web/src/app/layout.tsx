import type { Metadata, Viewport } from "next";
import Link from "next/link";
import {
  ClerkProvider,
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hangpost",
  description: "Make new friends in the city you just moved to.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <header className="flex items-center justify-between border-b border-black/10 px-6 py-3 dark:border-white/15">
            <Link href="/" className="font-semibold tracking-tight">
              Hangpost
            </Link>
            <nav className="flex items-center gap-3 text-sm">
              <Link href="/demo" className="opacity-70 hover:opacity-100">
                Demo
              </Link>
              <SignedOut>
                <SignInButton mode="modal">
                  <button className="rounded px-3 py-1 text-sm opacity-70 hover:opacity-100">
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton mode="modal" forceRedirectUrl="/profile/new">
                  <button className="rounded bg-foreground px-3 py-1 text-sm text-background">
                    Sign up
                  </button>
                </SignUpButton>
              </SignedOut>
              <SignedIn>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
            </nav>
          </header>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
