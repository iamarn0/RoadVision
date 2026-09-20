export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "operator" | "auditor" | string;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
};

export const SESSION_COOKIE = "roadvision_session";

export function roleLabel(role: string | undefined): string {
  switch (role) {
    case "admin":
      return "Administrator";
    case "operator":
      return "Operator";
    case "auditor":
      return "Auditor";
    default:
      return role || "Unknown";
  }
}

export function canUpload(role: string | undefined): boolean {
  return role === "admin" || role === "operator";
}

export function canManageUsers(role: string | undefined): boolean {
  return role === "admin";
}

export function canMutateJobs(role: string | undefined): boolean {
  return role === "admin" || role === "operator";
}
