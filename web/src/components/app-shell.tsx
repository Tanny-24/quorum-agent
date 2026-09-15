"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { BackendStatus } from "@/components/backend-status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navigation = [
  {
    label: "Workspace",
    items: [
      { label: "Overview", href: "/", marker: "O" },
      { label: "Demo Mode", href: "/demo", marker: "D" },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Shifts", href: "/shifts", marker: "S" },
      { label: "Volunteers", href: "/volunteers", marker: "V" },
    ],
  },
  {
    label: "Attention",
    items: [
      { label: "Human Decisions", href: "/human-decisions", marker: "H" },
      { label: "Pending Effects", href: "/pending-effects", marker: "P" },
    ],
  },
  {
    label: "Observability",
    items: [{ label: "Decision Feed", href: "/decision-feed", marker: "F" }],
  },
];

function SidebarContent({ close }: { close?: () => void }) {
  const pathname = usePathname();
  return (
    <>
      <div className="flex h-20 items-center gap-3 border-b border-white/10 px-5">
        <div className="grid size-9 place-items-center rounded-xl bg-blue-500 text-sm font-black text-white shadow-lg shadow-blue-950/20">
          Q
        </div>
        <div>
          <div className="text-sm font-bold tracking-[0.18em] text-white">QUORUM</div>
          <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">
            Operations
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-5" aria-label="Primary navigation">
        {navigation.map((group) => (
          <div className="mb-6" key={group.label}>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={close}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400",
                      active
                        ? "bg-white/10 text-white"
                        : "text-slate-400 hover:bg-white/5 hover:text-slate-100",
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    <span
                      className={cn(
                        "grid size-6 place-items-center rounded-md text-[10px] font-bold",
                        active ? "bg-blue-500 text-white" : "bg-white/5 text-slate-400",
                      )}
                      aria-hidden="true"
                    >
                      {item.marker}
                    </span>
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/10 p-4">
        <div className="rounded-xl bg-white/5 px-3 py-3">
          <p className="text-xs font-semibold text-slate-200">Attention-aware</p>
          <p className="mt-1 text-[11px] leading-4 text-slate-500">
            Human judgment is reserved for decisions that need it.
          </p>
        </div>
      </div>
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col bg-navy lg:flex">
        <SidebarContent />
      </aside>

      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <button
            className="absolute inset-0 bg-slate-950/45"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          />
          <aside className="relative flex h-full w-[min(82vw,300px)] flex-col bg-navy shadow-2xl">
            <SidebarContent close={() => setMenuOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label="Open navigation"
              onClick={() => setMenuOpen(true)}
            >
              <span className="flex w-5 flex-col gap-1" aria-hidden="true">
                <span className="h-0.5 w-5 bg-current" />
                <span className="h-0.5 w-5 bg-current" />
                <span className="h-0.5 w-5 bg-current" />
              </span>
            </Button>
            <div>
              <p className="text-sm font-semibold text-foreground">Riverside Food Bank</p>
              <p className="hidden text-xs text-muted-foreground sm:block">
                Community coordination workspace
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 sm:gap-5">
            <Badge className="border-violet/20 bg-violet-soft text-violet">
              Synthetic Demo
            </Badge>
            <div className="hidden sm:block">
              <BackendStatus />
            </div>
          </div>
        </header>
        <main className="mx-auto min-h-[calc(100vh-4rem)] max-w-[1480px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
