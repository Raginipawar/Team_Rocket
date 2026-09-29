import type { Metadata, Viewport } from "next";
import { Noto_Sans, Noto_Sans_Devanagari } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
import Providers from "./providers";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

const noto = Noto_Sans({ variable: "--font-noto", subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] });
const deva = Noto_Sans_Devanagari({ variable: "--font-deva", subsets: ["devanagari"], weight: ["400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: { default: "GoldenHour", template: "%s · GoldenHour" },
  description: "Emergency help for Pune and Pimpri Chinchwad: the nearest ambulance and a hospital that is ready for you.",
  manifest: "/manifest.webmanifest",
  applicationName: "GoldenHour",
  appleWebApp: { capable: true, title: "GoldenHour", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#dc2626",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <html lang={locale} className={`${noto.variable} ${deva.variable}`}>
      <body>
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
