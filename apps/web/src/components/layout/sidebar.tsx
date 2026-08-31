"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  Users,
  FileText,
  Calendar,
  FileCheck,
  DollarSign,
  Settings,
  BarChart3,
  Target,
  type LucideIcon,
} from "lucide-react";

import { QuantHireLogo } from "@/components/brand/QuantHireLogo";
import { cn } from "@/lib/utils";

type NavAccent = "red" | "teal" | "gold" | "slate";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  accent: NavAccent;
};

type NavGroup = {
  title: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Overview",
    items: [
      {
        label: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
        accent: "red",
      },
    ],
  },
  {
    title: "Talent",
    items: [
      { label: "Jobs", href: "/dashboard/jobs", icon: Briefcase, accent: "teal" },
      {
        label: "Candidates",
        href: "/dashboard/candidates",
        icon: Users,
        accent: "gold",
      },
      {
        label: "Match",
        href: "/dashboard/job-matching",
        icon: Target,
        accent: "red",
      },
    ],
  },
  {
    title: "Pipeline",
    items: [
      {
        label: "Applications",
        href: "/dashboard/applications",
        icon: FileText,
        accent: "teal",
      },
      {
        label: "Interviews",
        href: "/dashboard/interviews",
        icon: Calendar,
        accent: "red",
      },
      {
        label: "Assessments",
        href: "/dashboard/assessments",
        icon: FileCheck,
        accent: "slate",
      },
      {
        label: "Offers",
        href: "/dashboard/offers",
        icon: DollarSign,
        accent: "gold",
      },
    ],
  },
  {
    title: "Workspace",
    items: [
      {
        label: "Analytics",
        href: "/dashboard/analytics",
        icon: BarChart3,
        accent: "teal",
      },
      {
        label: "Settings",
        href: "/dashboard/settings",
        icon: Settings,
        accent: "slate",
      },
    ],
  },
];

const ACCENT_ICON: Record<NavAccent, string> = {
  red: "bg-brand-red/10 text-brand-red",
  teal: "bg-brand-teal/10 text-brand-teal",
  gold: "bg-brand-gold/15 text-amber-800 dark:text-brand-gold",
  slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

function isNavActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="hidden lg:flex w-[248px] shrink-0 flex-col border-r border-slate-200/80 bg-card dark:border-slate-800"
      aria-label="Primary navigation"
    >
      <div className="flex h-16 shrink-0 items-center border-b border-slate-200/80 px-3 dark:border-slate-800">
        <QuantHireLogo
          href="/dashboard"
          variant="nav"
          size="sm"
          surface="light"
          maxHeight={44}
          priority
          className="w-full max-w-[220px]"
          imageClassName="h-[44px] w-auto max-w-full object-contain"
        />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-5">
          {NAV_GROUPS.map((group) => (
            <div key={group.title}>
              <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {group.title}
              </p>
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const active = isNavActive(pathname, item.href);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
                          active
                            ? "bg-slate-900 text-white shadow-sm dark:bg-slate-100 dark:text-slate-900"
                            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                        )}
                      >
                        <span
                          className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors",
                            active
                              ? "bg-white/15 text-white dark:bg-slate-900/10 dark:text-slate-900"
                              : ACCENT_ICON[item.accent],
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </nav>

      <div className="shrink-0 border-t border-slate-200/80 px-4 py-3 dark:border-slate-800">
        <p className="text-[10px] text-muted-foreground">
          Agentic hiring · SSO secured
        </p>
      </div>
    </aside>
  );
}
