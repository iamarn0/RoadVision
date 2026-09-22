export type DistrictRef = {
  id: string;
  name: string;
};

export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "district_master" | "operator" | "auditor" | string;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
  districts?: DistrictRef[];
};

export const SESSION_COOKIE = "roadvision_session";

export function roleLabel(role: string | undefined): string {
  switch (role) {
    case "admin":
      return "Administrator";
    case "district_master":
      return "District master";
    case "operator":
      return "Operator";
    case "auditor":
      return "Auditor";
    default:
      return role || "Unknown";
  }
}

export function canUpload(role: string | undefined): boolean {
  return role === "admin" || role === "district_master" || role === "operator";
}

export function canDeleteVideos(role: string | undefined): boolean {
  return canUpload(role);
}

export function canManageUsers(role: string | undefined): boolean {
  return role === "district_master";
}

export function canMutateJobs(role: string | undefined): boolean {
  return role === "admin" || role === "district_master" || role === "operator";
}
