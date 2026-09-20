"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiGet, apiPost, ApiClientError } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  setUser: (user: AuthUser | null) => void;
  refresh: () => Promise<AuthUser | null>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await apiGet<AuthUser>("/api/auth/me");
      setUser(me);
      return me;
    } catch (err) {
      if (err instanceof ApiClientError && (err.errorCode === "UNAUTHENTICATED" || err.message)) {
        setUser(null);
      } else {
        setUser(null);
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    try {
      await apiPost("/api/auth/logout");
    } catch {
      /* ignore */
    }
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo(
    () => ({ user, loading, setUser, refresh, logout }),
    [user, loading, refresh, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
