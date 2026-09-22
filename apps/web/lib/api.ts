export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  errorCode: string;
  details: Record<string, unknown>;
  status: number;

  constructor(
    errorCode: string,
    message: string,
    details: Record<string, unknown> = {},
    status = 0,
  ) {
    super(message);
    this.errorCode = errorCode;
    this.details = details;
    this.status = status;
  }
}

async function parseError(response: Response): Promise<never> {
  let body: { error_code?: string; message?: string; details?: Record<string, unknown> } = {};
  try {
    body = await response.json();
  } catch {
    /* ignore */
  }
  const fallback =
    typeof (body as { detail?: unknown }).detail === "string"
      ? (body as { detail: string }).detail
      : `Request failed (${response.status})`;
  const error = new ApiClientError(
    body.error_code ?? "REQUEST_FAILED",
    body.message ?? fallback,
    body.details ?? {},
    response.status,
  );
  if (
    typeof window !== "undefined" &&
    response.status === 401 &&
    !window.location.pathname.startsWith("/login") &&
    window.location.pathname !== "/"
  ) {
    window.location.href = "/login";
  }
  throw error;
}

const defaultInit: RequestInit = {
  credentials: "include",
  cache: "no-store",
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...defaultInit });
  if (!response.ok) await parseError(response);
  return response.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...defaultInit,
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) await parseError(response);
  return response.json();
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...defaultInit,
    method: "PATCH",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) await parseError(response);
  return response.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...defaultInit, method: "DELETE" });
  if (!response.ok) await parseError(response);
  return response.json();
}

export function mediaUrl(assetId: string | null | undefined): string | null {
  if (!assetId) return null;
  return `${API_BASE}/api/media/${assetId}`;
}

export function formatSeconds(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  const total = Math.max(0, Math.floor(value));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export type VideoRead = {
  id: string;
  original_filename: string;
  file_size: number;
  mime_type: string | null;
  duration: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  frame_count: number | null;
  codec: string | null;
  status: string;
  source_type: string;
  original_asset_id?: string | null;
  district_id?: string | null;
  district_name?: string | null;
  created_at: string;
};

export type JobRead = {
  id: string;
  video_id: string;
  status: string;
  progress: number;
  current_frame: number;
  total_frames: number;
  processed_frames: number;
  skipped_frames: number;
  processing_fps: number | null;
  estimated_remaining_seconds: number | null;
  requested_device: string | null;
  actual_device: string | null;
  gpu_name: string | null;
  processing_profile: string;
  vehicles_detected: number;
  plates_detected: number;
  error_code: string | null;
  error_message: string | null;
  fallback_reason: string | null;
  created_at: string;
  source_filename?: string | null;
  annotated_asset_id?: string | null;
  original_asset_id?: string | null;
  source_fps?: number | null;
  live_frame_available?: boolean;
  paused?: boolean;
  district_id?: string | null;
  district_name?: string | null;
  metrics?: Record<string, unknown> | null;
};

export type LiveCaptureItem = {
  track_id: number;
  plate_url: string;
  vehicle_url: string;
  full_url?: string;
  updated_at: number;
  kind?: "plate" | "snapshot";
  label?: string;
  vehicle_type?: string | null;
  first_seen_seconds?: number;
  last_seen_seconds?: number;
  timestamp?: number;
  timestamp_overlay?: string | null;
  last_seen_overlay?: string | null;
  plate_confidence?: number | null;
  vehicle_confidence?: number | null;
};

export type CaptureJobResponse = JobRead & {
  snapshot?: LiveCaptureItem | null;
};

export type LiveCapturesResponse = {
  job_id: string;
  plates_captured: number;
  items: LiveCaptureItem[];
};

export type DetectionRead = {
  id: string;
  track_id: number;
  vehicle_type: string;
  normalized_plate_text: string | null;
  raw_ocr_text: string | null;
  ocr_confidence: number;
  plate_detection_confidence: number;
  vehicle_detection_confidence: number;
  status: string;
  first_seen_seconds: number;
  last_seen_seconds: number;
  first_seen_overlay?: string | null;
  last_seen_overlay?: string | null;
  best_frame_number: number | null;
  consistency_score: number | null;
  full_frame_asset_id: string | null;
  vehicle_crop_asset_id: string | null;
  plate_crop_asset_id: string | null;
};
