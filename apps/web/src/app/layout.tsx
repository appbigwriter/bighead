import type { Metadata } from "next";
import { getServerVisualPreferences } from "@/lib/server-visual-preferences";
import { visualPreferencesBootstrapScript } from "@/lib/theme-preference";
import "./globals.css";

export const metadata: Metadata = {
  title: "BigHead",
  description: "Workspace operacional do BigHead"
};

export default async function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const visualPreferences = await getServerVisualPreferences();
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <title>BigHead</title>
        <script
          dangerouslySetInnerHTML={{
            __html: visualPreferencesBootstrapScript(visualPreferences)
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
