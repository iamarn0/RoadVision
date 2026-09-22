"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, Mail, ShieldCheck } from "lucide-react";
import { ApiClientError, apiPost } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";

const fieldClass =
  "w-full rounded-md border border-[var(--border)] bg-white py-2.5 pl-10 pr-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

  if (loading || user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted)]">
        Checking session…
      </div>
    );
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden overflow-hidden bg-[#14210f] px-12 py-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(101,181,48,0.28),transparent_42%),radial-gradient(circle_at_bottom_right,rgba(101,181,48,0.18),transparent_40%)]" />
        <div className="relative">
          <p className="text-[11px] tracking-[0.28em] text-[#9bd36c]">ROADVISION</p>
          <h1 className="mt-6 max-w-md text-4xl font-semibold leading-tight">
            Vehicle intelligence for traffic operations
          </h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-white/70">
            Authorized district personnel can review ANPR jobs, uploaded footage, and plate evidence
            for the jurisdictions they are appointed to.
          </p>
        </div>
        <ul className="relative space-y-4 text-sm text-white/80">
          <li className="flex gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#9bd36c]" />
            Session access is issued by a district master. There is no public registration.
          </li>
          <li className="flex gap-3">
            <Lock className="mt-0.5 h-5 w-5 shrink-0 text-[#9bd36c]" />
            Footage and processing results stay scoped to appointed districts.
          </li>
        </ul>
      </aside>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[420px]">
          <a href="/" className="text-sm text-[var(--muted)] hover:text-[var(--accent)]">
            Back to homepage
          </a>
          <div className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--panel)] p-8 shadow-[0_18px_50px_rgba(20,33,15,0.08)]">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-md bg-[var(--hover)] text-[var(--accent)]">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <div>
                <p className="text-[11px] tracking-[0.22em] text-[var(--accent)]">ROADVISION</p>
                <h2 className="text-xl font-semibold text-[var(--text)]">Sign in to console</h2>
              </div>
            </div>
            <p className="mt-4 text-sm text-[var(--muted)]">
              Use the email and password issued for your district appointment.
            </p>

            <form className="mt-7 space-y-4" onSubmit={onSubmit}>
              <label className="block text-sm">
                <span className="font-medium text-[var(--text)]">Email</span>
                <span className="relative mt-1.5 block">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                  <input
                    className={fieldClass}
                    type="email"
                    autoComplete="username"
                    required
                    placeholder="name@example.gov"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </span>
              </label>
              <label className="block text-sm">
                <span className="font-medium text-[var(--text)]">Password</span>
                <span className="relative mt-1.5 block">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                  <input
                    className={`${fieldClass} pr-10`}
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-[var(--muted)] hover:text-[var(--text)]"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </span>
              </label>
              {error ? (
                <p className="rounded-md border border-[#c45c5c]/30 bg-[#f8ecec] px-3 py-2 text-sm text-[var(--danger)]">
                  {error}
                </p>
              ) : null}
              <button
                type="submit"
                disabled={pending}
                className="mt-2 w-full rounded-md bg-[var(--accent)] px-3 py-2.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {pending ? "Signing in…" : "Sign in"}
              </button>
            </form>
          </div>
          <p className="mt-6 text-center text-xs text-[var(--muted)]">
            Authorized use only. Accounts are provisioned by district masters.
          </p>
        </div>
      </section>
    </div>
  );
}
