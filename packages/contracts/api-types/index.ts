export type JobStatus =
  | "queued"
  | "uploading"
  | "validating"
  | "processing"
  | "finalizing"
  | "completed"
  | "failed"
  | "cancelled";

export type ConfidenceStatus =
  | "high_confidence"
  | "medium_confidence"
  | "low_confidence"
  | "uncertain"
  | "needs_verification";

export interface JobProgressEvent {
  job_id: string;
  status: JobStatus;
  progress: number;
  current_frame: number;
  total_frames: number;
  processing_fps: number | null;
  estimated_remaining_seconds: number | null;
  vehicles_detected: number;
  plates_detected: number;
  device: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface GpuStatus {
  cuda_available: boolean;
  device: string | null;
  gpu_name: string | null;
  total_memory_mb: number | null;
  available_memory_mb: number | null;
  torch_version: string | null;
  cuda_version: string | null;
  fp16_enabled: boolean;
  status: "ready" | "cpu_fallback" | "unavailable" | "configuration_error";
  fallback_reason?: string | null;
}

export interface ApiError {
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
}

export type UserRole = "admin" | "operator" | "auditor";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole | string;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
}
