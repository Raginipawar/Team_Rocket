import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { EASE } from "./motion";

interface RevealProps {
  children: ReactNode;
  delay?: number;
  className?: string;
}

export default function Reveal({ children, delay = 0, className }: RevealProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.32, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
