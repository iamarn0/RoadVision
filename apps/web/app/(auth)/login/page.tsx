"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiClientError, apiPost } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";
import { Button, TextField } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const nextUser = await apiPost<AuthUser>("/api/auth/login", { email, password });
      setUser(nextUser);
      router.replace("/dashboard");
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : "Unable to sign in. Check your credentials.";
      setError(message);
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-[var(--muted)]">Checking session…</div>;
  }

  if (user) {
    return null;
  }

  return (
    <div className="w-full max-w-md">
      <div className="mb-8 text-center">
        <p className="text-[11px] tracking-[0.2em] text-[var(--accent)]">ROADVISION</p>
        <h1 className="mt-2 text-2xl font-medium text-[var(--text)]">ANPR operations console</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Sign in with the account issued by your administrator. There is no public registration.
        </p>
        <a href="/" className="mt-3 inline-block text-sm text-[var(--accent)] hover:underline">
          Back to homepage
        </a>
      </div>

      <div className="rounded-sm border border-[var(--border)] bg-[var(--panel)] p-6 shadow-sm">
        <h2 className="text-base font-medium text-[var(--text)]">Sign in</h2>
        <form className="mt-5 space-y-4" onSubmit={onSubmit}>
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
