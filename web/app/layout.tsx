import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LexGraph — Contract intelligence",
  description: "Ask questions across agreements and see the evidence behind every answer.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
