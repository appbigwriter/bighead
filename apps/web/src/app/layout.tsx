import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BigHead",
  description: "Workspace operacional do BigHead"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('bighead-theme');document.documentElement.dataset.theme=t==='radar-dark'?'radar-dark':'aurora-light'}catch(e){}"
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
