import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

// Pill buttons from the website, sized for thumbs: md 52px, lg 60px, xl 72px.
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2.5 rounded-full font-semibold transition active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none select-none text-center",
  {
    variants: {
      variant: {
        primary: "bg-ink text-bg hover:opacity-90",
        danger: "bg-red text-white hover:brightness-95 dark:text-white",
        success: "bg-green text-white hover:brightness-95 dark:bg-green-600",
        soft: "bg-soft text-ink hover:bg-soft-2",
        outline: "border-2 border-line bg-card text-ink hover:bg-soft",
        dangerOutline: "border-2 border-red text-red-ink bg-card hover:bg-red-soft",
        ghost: "text-ink hover:bg-soft",
        link: "text-ink underline underline-offset-4 decoration-2 rounded-md px-1",
      },
      // min-h, not h: a fixed height with no overflow handling meant a
      // longer label (e.g. "Patient got worse" + an icon, inside a narrow
      // 2-column grid on a phone) that wraps to 2 lines just overflowed
      // silently past the button's bottom edge, visually overlapping
      // whatever sat below it -- confirmed from a real screenshot. A
      // min-height lets a button that genuinely needs 2 lines grow instead,
      // while staying the same single-line height everywhere else.
      size: {
        sm: "min-h-10 px-4 py-2 text-[15px]",
        md: "min-h-[52px] px-6 py-2 text-[17px]",
        lg: "min-h-[60px] px-7 py-2.5 text-[19px]",
        xl: "min-h-[72px] px-8 py-3 text-[21px]",
        icon: "h-12 w-12 p-0",
      },
      block: { true: "w-full" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type Props = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean; loading?: boolean };

export function Button({ className, variant, size, block, asChild, loading, children, disabled, ...props }: Props) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp className={cn(buttonVariants({ variant, size, block }), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {asChild ? children : (
        <>
          {loading ? <span className="h-5 w-5 animate-spin rounded-full border-[3px] border-current border-t-transparent" aria-hidden /> : null}
          {children}
        </>
      )}
    </Comp>
  );
}
