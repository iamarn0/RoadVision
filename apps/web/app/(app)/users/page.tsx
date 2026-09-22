"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiGet, apiPatch, apiPost, ApiClientError } from "@/lib/api";
import type { AuthUser, DistrictRef } from "@/lib/auth";
import { canManageUsers, roleLabel } from "@/lib/auth";
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

function DistrictPicker({
  options,
  selected,
  onChange,
  locked = [],
}: {
  options: DistrictRef[];
  selected: string[];
  onChange: (ids: string[]) => void;
  locked?: DistrictRef[];
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const selectedSet = new Set(selected);
  const selectedDistricts = options.filter((district) => selectedSet.has(district.id));
  const filtered = options.filter((district) => !q || district.name.toLowerCase().includes(q));

  function toggle(id: string) {
    if (selectedSet.has(id)) {
      onChange(selected.filter((item) => item !== id));
      return;
    }
    onChange([...selected, id]);
  }

  return (
    <div className="space-y-2">
      <TextField
        label="Districts"
        placeholder="Search West Bengal districts"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <p className="text-xs text-[var(--muted)]">
        Tick one or more districts. {selectedDistricts.length} selected.
      </p>
      {selectedDistricts.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {selectedDistricts.map((district) => (
            <Badge key={district.id} className="inline-flex items-center gap-1">
              {district.name}
              <button
                type="button"
                className="text-[var(--muted)] hover:text-[var(--text)]"
                aria-label={`Remove ${district.name}`}
                onClick={() => toggle(district.id)}
              >
                ×
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
      {locked.length > 0 ? (
        <p className="text-xs text-[var(--muted)]">
          Also appointed elsewhere: {locked.map((d) => d.name).join(", ")}
        </p>
      ) : null}
      <div className="max-h-48 overflow-y-auto rounded-sm border border-[var(--border)]">
        {filtered.length === 0 ? (
          <p className="px-3 py-2 text-sm text-[var(--muted)]">No matching districts.</p>
        ) : (
          filtered.map((district) => {
            const checked = selectedSet.has(district.id);
            return (
              <label
                key={district.id}
                className="flex cursor-pointer items-center gap-2 border-b border-[var(--border)] px-3 py-2 text-sm last:border-b-0"
              >
                <input type="checkbox" checked={checked} onChange={() => toggle(district.id)} />
                <span>{district.name}</span>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
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
  const [issueDistricts, setIssueDistricts] = useState<string[]>([]);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [issuedEmail, setIssuedEmail] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmAction>(null);
  const [copied, setCopied] = useState(false);
  const [appointUser, setAppointUser] = useState<AuthUser | null>(null);
  const [appointDistricts, setAppointDistricts] = useState<string[]>([]);

  useEffect(() => {
    if (user && !canManageUsers(user.role)) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  const catalog = useQuery({
    queryKey: ["districts"],
    queryFn: () => apiGet<DistrictRef[]>("/api/districts"),
    enabled: canManageUsers(user?.role),
  });
  const catalogDistricts = catalog.data ?? [];

  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<AuthUser[]>("/api/users"),
    enabled: canManageUsers(user?.role),
  });

  const filtered = useMemo(() => {
    const rows = users.data ?? [];
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (roleFilter !== "all" && row.role !== roleFilter) return false;
      if (statusFilter === "active" && !row.is_active) return false;
      if (statusFilter === "disabled" && row.is_active) return false;
      if (!q) return true;
      const districtHit = (row.districts ?? []).some((district) => district.name.toLowerCase().includes(q));
      return (
        row.email.toLowerCase().includes(q) ||
        row.display_name.toLowerCase().includes(q) ||
        row.role.toLowerCase().includes(q) ||
        districtHit
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
        district_ids: issueDistricts,
      }),
    onSuccess: (data) => {
      setTempPassword(data.temporary_password);
      setIssuedEmail(data.user.email);
      setEmail("");
      setDisplayName("");
      setRole("operator");
      setPassword("");
      setConfirmPassword("");
      setIssueDistricts([]);
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
      setAppointUser(null);
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
    if (issueDistricts.length === 0) {
      setFormError("Appoint at least one district.");
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

  if (!canManageUsers(user?.role)) {
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
            Issue and manage console access for operators and auditors in your appointed districts.
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
            placeholder="Name, email, or district"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <SelectField
            label="Role"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="all">All roles</option>
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
                <th className="px-4 py-3 font-medium">Districts</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last login</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 text-[var(--text)]">{row.display_name}</td>
                  <td className="px-4 py-3">{row.email}</td>
                  <td className="px-4 py-3">
                    <select
                      value={row.role}
                      disabled={row.id === user?.id || patchMutation.isPending}
                      onChange={(e) =>
                        patchMutation.mutate({ id: row.id, body: { role: e.target.value } })
                      }
                      className="rounded-sm border border-[var(--border)] bg-[var(--panel)] px-2 py-1 text-xs"
                      aria-label={`Role for ${row.display_name}`}
                    >
                      <option value="operator">Operator</option>
                      <option value="auditor">Auditor</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-1">
                      {(row.districts ?? []).map((district) => (
                        <Badge key={district.id}>{district.name}</Badge>
                      ))}
                      <button
                        type="button"
                        className="text-xs text-[var(--accent)] hover:underline"
                        onClick={() => {
                          setAppointUser(row);
                          setAppointDistricts((row.districts ?? []).map((district) => district.id));
                        }}
                      >
                        Edit
                      </button>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      className={
                        row.is_active
                          ? "border-[#3d9a6a]/40 text-[#3d9a6a]"
                          : "border-[#c45c5c]/40 text-[#c45c5c]"
                      }
                    >
                      {row.is_active ? "Active" : "Disabled"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{formatLastLogin(row.last_login_at)}</td>
                  <td className="space-x-2 px-4 py-3 whitespace-nowrap">
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] hover:text-[var(--accent)] disabled:opacity-40"
                      disabled={row.id === user?.id}
                      onClick={() =>
                        setConfirm({
                          type: row.is_active ? "disable" : "enable",
                          user: row,
                        })
                      }
                    >
                      {row.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] hover:text-[var(--accent)]"
                      onClick={() => setConfirm({ type: "reset", user: row })}
                    >
                      Reset password
                    </button>
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] hover:text-[var(--accent)]"
                      onClick={() => setConfirm({ type: "revoke", user: row })}
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
          Create an operator or auditor and appoint them to one or more districts.
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
          </SelectField>
          <DistrictPicker options={catalogDistricts} selected={issueDistricts} onChange={setIssueDistricts} />
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
        open={Boolean(appointUser)}
        title={appointUser ? `Appoint districts · ${appointUser.display_name}` : "Appoint districts"}
        onClose={() => setAppointUser(null)}
      >
        <DistrictPicker
          options={catalogDistricts}
          selected={appointDistricts}
          onChange={setAppointDistricts}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => setAppointUser(null)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={patchMutation.isPending || !appointUser}
            onClick={() => {
              if (!appointUser) return;
              patchMutation.mutate({ id: appointUser.id, body: { district_ids: appointDistricts } });
            }}
          >
            {patchMutation.isPending ? "Saving…" : "Save appointments"}
          </Button>
        </div>
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
