import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { PHONE_EASE } from "./motion";

interface PhoneFrameProps {
  children: ReactNode;
  delay?: number;
  label: string;
  className?: string;
}

/** citizen.com's phone frame: elliptical 13% / 6% corners, an 8px dark ring,
 *  and a slow 2rem slide up as it enters the screen. */
export default function PhoneFrame({ children, delay = 0, label, className }: PhoneFrameProps) {
  return (
    <motion.div
      className={`phone${className ? ` ${className}` : ""}`}
      role="img"
      aria-label={label}
      initial={{ opacity: 0, y: 32 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{
        y: { duration: 1.5, delay: 0.25 + delay, ease: PHONE_EASE },
        opacity: { duration: 1, delay: 0.25 + delay, ease: "easeOut" },
      }}
    >
      <div className="phone-screen">
        <div className="phone-notch" />
        {children}
      </div>
    </motion.div>
  );
}
