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
  Upload,
  Users,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { canManageUsers, canUpload, roleLabel } from "@/lib/auth";

type NavItem = { href: string; label: string; icon: typeof LayoutDashboard; roles?: string[] };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/videos", label: "Videos", icon: FolderOpen },
  { href: "/videos/upload", label: "Upload", icon: Upload, roles: ["admin", "operator"] },
  { href: "/jobs", label: "Processing", icon: Activity },
  { href: "/users", label: "Personnel", icon: Users, roles: ["admin"] },
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

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const health = useQuery({
    queryKey: ["health-live"],
    queryFn: fetchLive,
    refetchInterval: 15000,
  });

  const operational = health.data?.status === "ok";
  const role = user?.role;
  const visibleNav = NAV.filter((item) => {
    if (!item.roles) return true;
    if (item.href === "/videos/upload") return canUpload(role);
    if (item.href === "/users") return canManageUsers(role);
    return item.roles.includes(role || "");
  });

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[#2a3441] bg-[#121821]">
        <div className="border-b border-[#2a3441] px-4 py-4">
          <p className="text-[11px] tracking-[0.18em] text-[#9aa8b5]">ROADVISION</p>
          <p className="mt-1 text-sm text-[#e8edf2]">ANPR operations</p>
          <p className="mt-2 text-xs text-[#9aa8b5]">v{process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0"}</p>
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
                  active ? "bg-[#1d2836] text-white" : "text-[#c5d0da] hover:bg-[#1a222d]"
                }`}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={16} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-[#2a3441] px-4 py-3 text-sm">
          {user ? (
            <div className="mb-3">
              <p className="truncate text-sm text-[#e8edf2]">{user.display_name}</p>
              <p className="truncate text-xs text-[#9aa8b5]">
                {roleLabel(user.role)} · {user.email}
              </p>
              <button
                type="button"
                onClick={() => void logout()}
                className="mt-2 flex items-center gap-1 text-xs text-[#9aa8b5] hover:text-white"
              >
                <LogOut size={12} aria-hidden="true" />
                Sign out
              </button>
            </div>
          ) : null}
          <p className="text-xs uppercase tracking-wide text-[#9aa8b5]">System status</p>
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
