"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { apiGet, apiPatch, apiPost, ApiClientError } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";
import { roleLabel } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Modal,
  SelectField,
  Skeleton,
  TextField,
} from "@/components/ui";

type UserCreated = { user: AuthUser; temporary_password: string };

type ConfirmAction =
  | { type: "disable" | "enable" | "reset" | "revoke"; user: AuthUser }
  | null;

function formatLastLogin(value: string | null): string {
  if (!value) return "Never";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function PersonnelPage() {
  const { user } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [issueOpen, setIssueOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("operator");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [issuedEmail, setIssuedEmail] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmAction>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.replace("/dashboard");
    }
  }, [user, router]);

  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<AuthUser[]>("/api/users"),
    enabled: user?.role === "admin",
  });

  const filtered = useMemo(() => {
    const rows = users.data ?? [];
    const q = search.trim().toLowerCase();
    return rows.filter((u) => {
      if (roleFilter !== "all" && u.role !== roleFilter) return false;
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "disabled" && u.is_active) return false;
      if (!q) return true;
      return (
        u.email.toLowerCase().includes(q) ||
        u.display_name.toLowerCase().includes(q) ||
        u.role.toLowerCase().includes(q)
      );
    });
  }, [users.data, search, roleFilter, statusFilter]);

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<UserCreated>("/api/users", {
        email,
        display_name: displayName,
        role,
        password,
      }),
    onSuccess: (data) => {
      setTempPassword(data.temporary_password);
      setIssuedEmail(data.user.email);
      setEmail("");
      setDisplayName("");
      setRole("operator");
      setPassword("");
      setConfirmPassword("");
      setFormError(null);
      setIssueOpen(false);
      void qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err) => {
      setFormError(err instanceof ApiClientError ? err.message : "Failed to issue access");
    },
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiPatch<AuthUser>(`/api/users/${id}`, body),
    onSuccess: () => {
      setConfirm(null);
      void qc.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const resetMutation = useMutation({
    mutationFn: (id: string) => apiPost<UserCreated>(`/api/users/${id}/reset-password`),
    onSuccess: (data) => {
      setConfirm(null);
      setTempPassword(data.temporary_password);
      setIssuedEmail(data.user.email);
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiPost<{ revoked: number }>(`/api/users/${id}/revoke-sessions`),
    onSuccess: () => {
      setConfirm(null);
      void qc.invalidateQueries({ queryKey: ["users"] });
    },
  });

  function onIssue(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setFormError("Password and confirmation do not match.");
      return;
    }
    createMutation.mutate();
  }

  async function copyTempPassword() {
    if (!tempPassword) return;
    try {
      await navigator.clipboard.writeText(tempPassword);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  function runConfirm() {
    if (!confirm) return;
    if (confirm.type === "disable" || confirm.type === "enable") {
      patchMutation.mutate({
        id: confirm.user.id,
        body: { is_active: confirm.type === "enable" },
      });
      return;
    }
    if (confirm.type === "reset") {
      resetMutation.mutate(confirm.user.id);
      return;
    }
    revokeMutation.mutate(confirm.user.id);
  }

  if (user?.role !== "admin") {
    return <Skeleton className="h-64" />;
  }

  const confirmPending =
    patchMutation.isPending || resetMutation.isPending || revokeMutation.isPending;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-medium">Personnel</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Issue and manage console access for authorized operators and auditors.
          </p>
        </div>
        <Button type="button" onClick={() => setIssueOpen(true)}>
          Issue access
        </Button>
      </div>

      <Card>
        <div className="grid gap-3 md:grid-cols-4">
          <TextField
            label="Search"
            placeholder="Name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <SelectField
            label="Role"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="all">All roles</option>
            <option value="admin">Administrator</option>
            <option value="operator">Operator</option>
            <option value="auditor">Auditor</option>
          </SelectField>
          <SelectField
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </SelectField>
          <div className="flex items-end text-sm text-[var(--muted)]">
            {filtered.length} account{filtered.length === 1 ? "" : "s"}
          </div>
        </div>
      </Card>

      {users.isLoading ? <Skeleton className="h-48" /> : null}
      {users.isError ? (
        <p className="text-sm text-[#c45c5c]">Unable to load personnel.</p>
      ) : null}

      {!users.isLoading && filtered.length === 0 ? (
        <EmptyState
          title="No matching personnel"
          description="Adjust filters or issue access for a new operator."
        />
      ) : null}

      {filtered.length > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last login</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 text-[var(--text)]">{u.display_name}</td>
                  <td className="px-4 py-3">{u.email}</td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      disabled={u.id === user.id || patchMutation.isPending}
                      onChange={(e) =>
                        patchMutation.mutate({ id: u.id, body: { role: e.target.value } })
                      }
                      className="rounded-sm border border-[var(--border)] bg-[var(--panel)] px-2 py-1 text-xs"
                      aria-label={`Role for ${u.display_name}`}
                    >
                      <option value="admin">Administrator</option>
                      <option value="operator">Operator</option>
                      <option value="auditor">Auditor</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      className={
                        u.is_active
                          ? "border-[#3d9a6a]/40 text-[#3d9a6a]"
                          : "border-[#c45c5c]/40 text-[#c45c5c]"
                      }
                    >
                      {u.is_active ? "Active" : "Disabled"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{formatLastLogin(u.last_login_at)}</td>
                  <td className="space-x-2 px-4 py-3 whitespace-nowrap">
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] hover:text-[var(--accent)] disabled:opacity-40"
                      disabled={u.id === user.id}
                      onClick={() =>
                        setConfirm({
                          type: u.is_active ? "disable" : "enable",
                          user: u,
                        })
                      }
                    >
                      {u.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] hover:text-[var(--accent)]"
                      onClick={() => setConfirm({ type: "reset", user: u })}
                    >
                      Reset password
                    </button>
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] hover:text-[var(--accent)]"
                      onClick={() => setConfirm({ type: "revoke", user: u })}
                    >
                      Revoke sessions
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      <Modal
        open={issueOpen}
        title="Issue console access"
        onClose={() => {
          setIssueOpen(false);
          setFormError(null);
          setPassword("");
          setConfirmPassword("");
        }}
      >
        <p className="mb-4 text-sm text-[var(--muted)]">
          Create an account for authorized personnel. Set an initial password to share securely.
        </p>
        <form className="space-y-3" onSubmit={onIssue}>
          <TextField
            label="Full name"
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
          <TextField
            label="Email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <SelectField label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="operator">Operator</option>
            <option value="auditor">Auditor</option>
            <option value="admin">Administrator</option>
          </SelectField>
          <TextField
            label="Initial password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <TextField
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
          {formError ? <p className="text-sm text-[#c45c5c]">{formError}</p> : null}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setIssueOpen(false);
                setFormError(null);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Issuing…" : "Issue access"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(tempPassword)}
        title="Access issued"
        onClose={() => {
          setTempPassword(null);
          setIssuedEmail(null);
          setCopied(false);
        }}
      >
        <p className="text-sm text-[var(--muted)]">
          Account created for {issuedEmail ?? "the user"}. Confirm the initial password below before
          closing — it will not be shown again.
        </p>
        <code className="mt-3 block rounded-sm bg-[var(--hover)] px-3 py-3 font-mono text-sm text-[var(--success)]">
          {tempPassword}
        </code>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => void copyTempPassword()}>
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button
            type="button"
            onClick={() => {
              setTempPassword(null);
              setIssuedEmail(null);
              setCopied(false);
            }}
          >
            Done
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(confirm)}
        title={
          confirm?.type === "disable"
            ? "Disable account"
            : confirm?.type === "enable"
              ? "Enable account"
              : confirm?.type === "reset"
                ? "Reset password"
                : "Revoke sessions"
        }
        message={
          confirm?.type === "disable"
            ? `Disable access for ${confirm.user.display_name} (${roleLabel(confirm.user.role)})? They will be signed out immediately.`
            : confirm?.type === "enable"
              ? `Re-enable access for ${confirm.user.display_name}?`
              : confirm?.type === "reset"
                ? `Reset password for ${confirm.user.display_name}? A new password will be shown once and all sessions will be revoked.`
                : confirm
                  ? `Revoke all active sessions for ${confirm.user.display_name}?`
                  : ""
        }
        confirmLabel={
          confirm?.type === "disable"
            ? "Disable"
            : confirm?.type === "enable"
              ? "Enable"
              : confirm?.type === "reset"
                ? "Reset password"
                : "Revoke sessions"
        }
        danger={confirm?.type === "disable" || confirm?.type === "reset"}
        pending={confirmPending}
        onCancel={() => setConfirm(null)}
        onConfirm={runConfirm}
      />
    </section>
  );
}
