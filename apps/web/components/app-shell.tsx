"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Settings,
  Users,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { canManageUsers, roleLabel } from "@/lib/auth";

type NavItem = { href: string; label: string; icon: typeof LayoutDashboard; roles?: string[] };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/videos", label: "Videos", icon: FolderOpen },
  { href: "/jobs", label: "Processing", icon: Activity },
  { href: "/users", label: "Personnel", icon: Users, roles: ["district_master"] },
  { href: "/settings", label: "Settings", icon: Settings },
];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function fetchLive(): Promise<{ status?: string } | null> {
  try {
    const response = await fetch(`${API_BASE}/health/live`, { cache: "no-store" });
    if (!response.ok) {
      return { status: "unavailable" };
    }
    return response.json();
  } catch {
    return { status: "unavailable" };
  }
}

async function fetchAppVersion(): Promise<{ version?: string } | null> {
  try {
    const response = await fetch(`${API_BASE}/api/version`, { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch {
    return null;
  }
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const health = useQuery({
    queryKey: ["health-live"],
    queryFn: fetchLive,
    refetchInterval: 15000,
  });
  const appVersion = useQuery({
    queryKey: ["app-version"],
    queryFn: fetchAppVersion,
  });

  const operational = health.data?.status === "ok";
  const role = user?.role;
  const visibleNav = NAV.filter((item) => {
    if (!item.roles) return true;
    if (item.href === "/users") return canManageUsers(role);
    return item.roles.includes(role || "");
  });

  return (
    <div className="flex min-h-screen bg-[var(--bg)]">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--panel)]">
        <div className="border-b border-[var(--border)] px-4 py-4">
          <a href="/" className="text-[11px] tracking-[0.18em] text-[var(--accent)]">
            ROADVISION
          </a>
          <p className="mt-1 text-sm text-[var(--text)]">ANPR operations</p>
          <p className="mt-2 text-xs text-[var(--muted)]">
            {appVersion.data?.version ? `v${appVersion.data.version}` : "\u00a0"}
          </p>
        </div>
        <nav className="flex-1 px-2 py-3" aria-label="Primary">
          {visibleNav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`mb-1 flex items-center gap-2 rounded-sm px-3 py-2 text-sm ${
                  active
                    ? "bg-[var(--accent)] text-white"
                    : "text-[var(--text)] hover:bg-[var(--hover)]"
                }`}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={16} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-[var(--border)] px-4 py-3 text-sm">
          {user ? (
            <div className="mb-3">
              <p className="truncate text-sm text-[var(--text)]">{user.display_name}</p>
              <p className="truncate text-xs text-[var(--muted)]">
                {roleLabel(user.role)} · {user.email}
              </p>
              <button
                type="button"
                onClick={() => void logout()}
                className="mt-2 flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--accent)]"
              >
                <LogOut size={12} aria-hidden="true" />
                Sign out
              </button>
            </div>
          ) : null}
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">System status</p>
          <p className="mt-1 flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${operational ? "bg-[#3d9a6a]" : "bg-[#c9922a]"}`}
              aria-hidden="true"
            />
            <span>{operational ? "Operational" : "Unavailable"}</span>
          </p>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">{children}</main>
    </div>
  );
}
