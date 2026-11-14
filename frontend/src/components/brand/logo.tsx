import { useId } from "react";

/** Repurpora mark: a benzene-like ring that "re-opens" (repurposing) around a spark. */
export function RepurporaMark({ className, size = 32 }: { className?: string; size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={className} aria-hidden>
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#14B8A6" />
          <stop offset="1" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
      <path d="M12.95,36 L12.95,43 L32,54 L51.05,43 L51.05,21 L32,10 L12.95,21" fill="none" stroke={`url(#g${id})`}
        strokeWidth="4.2" strokeLinejoin="round" strokeLinecap="round" />
      <polygon points="7.2,36.5 18.7,36.5 12.95,28" fill={`url(#g${id})`} />
      <g fill={`url(#g${id})`}>
        <circle cx="32" cy="10" r="4" /><circle cx="51.05" cy="21" r="4" /><circle cx="51.05" cy="43" r="4" />
        <circle cx="32" cy="54" r="4" /><circle cx="12.95" cy="43" r="4" /><circle cx="12.95" cy="21" r="4" />
      </g>
      <path d="M32,21 Q34,30 43,32 Q34,34 32,43 Q30,34 21,32 Q30,30 32,21Z" fill="#F5B642" />
    </svg>
  );
}

export function RepurporaWordmark({ className, dark = false }: { className?: string; dark?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className ?? ""}`}>
      <RepurporaMark size={30} />
      <span className={`text-xl font-bold tracking-tight ${dark ? "text-white" : "text-indigo-950"}`}>repurpora</span>
    </span>
  );
}
