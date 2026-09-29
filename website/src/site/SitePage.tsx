import { useEffect } from "react";
import Header from "../components/Header";
import Hero from "../components/Hero";
import HowItWorks from "../components/HowItWorks";
import { Closing, Coverage, Faq, Footer, Highlights, Safety, TwoApps } from "../components/Sections";

/** The public marketing website. */
export default function SitePage() {
  // The apps use hash routes (#/app, #/crew …). In-page links like "#how" scroll instead of routing.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element).closest?.("a[href^='#']") as HTMLAnchorElement | null;
      if (!a) return;
      const id = a.getAttribute("href")!.slice(1);
      if (!id || id.startsWith("/")) return;
      e.preventDefault();
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: "smooth" });
      else window.scrollTo({ top: 0, behavior: "smooth" });
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  return (
    <>
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <TwoApps />
        <Highlights />
        <Safety />
        <Coverage />
        <Faq />
        <Closing />
      </main>
      <Footer />
    </>
  );
}
