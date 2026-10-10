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
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
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
        {/* key={locale} forces a full remount of everything below on a
            language switch -- without it, React re-renders the existing
            component tree in place (same component type/position = update,
            not remount), so any component with locale-derived state set up
            once in useState/useEffect (a disabled flag, a bound handler)
            can get stuck on the old language's values instead of
            reinitializing. This was the real cause of "buttons go inactive
            after switching language" -- not a missing translation key
            (verified: en/hi/mr have the exact same 270 keys each). */}
        <NextIntlClientProvider key={locale}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
