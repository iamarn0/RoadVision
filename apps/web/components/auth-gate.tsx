"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";

export function AuthGate({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/dashboard")}`);
    }
  }, [loading, user, router, pathname]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0b0f14] text-sm text-[#9aa8b5]">
        Checking session…
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
