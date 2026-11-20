import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "MUSECUT — Music video to reels", description: "Turn music videos and lyrics into short-form videos automatically." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
