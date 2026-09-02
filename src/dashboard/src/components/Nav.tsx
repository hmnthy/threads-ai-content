"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Minimal top nav — full sidebar (docs/claude/design-system.md "Trang & Navigation")
// is out of scope tonight; only 2 pages exist so far.
const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/topics", label: "Topic Explorer" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1 border-b border-bg-border px-6 py-3">
      <span className="mr-4 text-[13px] font-semibold uppercase tracking-wide text-text-muted">
        Threads AI Content
      </span>
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
              active
                ? "bg-accent-purple text-text-primary"
                : "text-text-secondary hover:bg-bg-elevated hover:text-text-primary"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
