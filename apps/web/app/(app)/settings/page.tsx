"use client";

import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, apiPost, ApiClientError } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";
import { roleLabel } from "@/lib/auth";
import { Button, Card, Skeleton, TextField } from "@/components/ui";

type AppVersion = {
  name: string;
  version: string;
  commit: string;
  environment: string;
};

type SettingsPublic = {
  app_version: string;
  processing_profile: string;
  inference_image_size: number;
  frame_skip: number;
  ocr_interval_frames: number;
  vehicle_confidence: number;
  plate_confidence: number;
  high_confidence_threshold: number;
  medium_confidence_threshold: number;
  processing_device: string;
  use_half_precision: boolean;
  ocr_engine: string;
  storage_backend: string;
  retention_days: number;
  vehicle_model_configured: boolean;
  plate_model_configured: boolean;
  authentication_enabled: boolean;
};

export default function SettingsPage() {
  const { user, refresh, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [pwMessage, setPwMessage] = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);

  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiGet<SettingsPublic>("/api/settings"),
  });
  const appVersion = useQuery({
    queryKey: ["app-version"],
    queryFn: () => apiGet<AppVersion>("/api/version"),
  });

  async function onChangePassword(event: FormEvent) {
    event.preventDefault();
    setPwError(null);
    setPwMessage(null);
    try {
      await apiPost("/api/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setPwMessage("Password updated.");
      await refresh();
    } catch (err) {
      setPwError(err instanceof ApiClientError ? err.message : "Password change failed");
    }
  }

  if (settings.isLoading) return <Skeleton className="h-64" />;
  if (settings.isError || !settings.data) {
    return <p className="text-[#c45c5c]">Unable to load settings.</p>;
  }

  const s = settings.data;

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-xl font-medium">Settings</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Runtime configuration for RoadVision v{s.app_version}. Secrets are never displayed.
        </p>
      </div>

      <Card>
        <h2 className="text-sm font-medium">System information</h2>
        <ul className="mt-3 space-y-1 text-sm">
          <li>Version: {appVersion.data?.version ?? s.app_version}</li>
          <li>Commit: {appVersion.data?.commit ?? "unknown"}</li>
          <li>Environment: {appVersion.data?.environment ?? "—"}</li>
        </ul>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-medium">Processing</h2>
          <ul className="mt-3 space-y-1 text-sm">
            <li>Profile: {s.processing_profile}</li>
            <li>Inference resolution: {s.inference_image_size}</li>
            <li>Frame skip: {s.frame_skip}</li>
            <li>OCR interval: {s.ocr_interval_frames}</li>
            <li>Vehicle confidence: {s.vehicle_confidence}</li>
            <li>Plate confidence: {s.plate_confidence}</li>
            <li>
              High / medium thresholds: {s.high_confidence_threshold} / {s.medium_confidence_threshold}
            </li>
          </ul>
        </Card>
        <Card>
          <h2 className="text-sm font-medium">AI models</h2>
          <ul className="mt-3 space-y-1 text-sm">
            <li>Vehicle model: {s.vehicle_model_configured ? "configured" : "not configured"}</li>
            <li>Plate model: {s.plate_model_configured ? "configured" : "not configured"}</li>
            <li>OCR engine: {s.ocr_engine}</li>
            <li>Device: {s.processing_device}</li>
            <li>FP16: {s.use_half_precision ? "enabled" : "disabled"}</li>
          </ul>
        </Card>
        <Card>
          <h2 className="text-sm font-medium">Storage</h2>
          <ul className="mt-3 space-y-1 text-sm">
            <li>Backend: {s.storage_backend}</li>
            <li>Retention days: {s.retention_days}</li>
          </ul>
        </Card>
        <Card>
          <h2 className="text-sm font-medium">Account</h2>
          <ul className="mt-3 space-y-1 text-sm">
            <li>
              Signed in: {user?.display_name ?? "—"} ({roleLabel(user?.role)})
            </li>
            <li>Email: {user?.email ?? "—"}</li>
            <li>
              Authentication: {s.authentication_enabled ? "enabled" : "disabled (test mode)"}
            </li>
          </ul>
          <form className="mt-4 space-y-3" onSubmit={onChangePassword}>
            <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Change password</p>
            <TextField
              label="Current password"
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <TextField
              label="New password"
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            {pwMessage ? <p className="text-sm text-[#3d9a6a]">{pwMessage}</p> : null}
            {pwError ? <p className="text-sm text-[#c45c5c]">{pwError}</p> : null}
            <Button type="submit">Update password</Button>
          </form>
          <div className="mt-6 border-t border-[var(--border)] pt-4">
            <Button type="button" variant="danger" onClick={() => void logout()}>
              Sign out
            </Button>
          </div>
        </Card>
      </div>
    </section>
  );
}
