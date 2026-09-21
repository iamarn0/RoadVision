"use client";

import { useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { API_BASE, ApiClientError, apiPost, formatBytes, type JobRead, type VideoRead } from "@/lib/api";
import { Button, Card } from "@/components/ui";

const ALLOWED = ["mp4", "avi", "mov", "mkv", "webm"];

type LocalMeta = {
  name: string;
  size: number;
  type: string;
  duration?: number;
  width?: number;
  height?: number;
};

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<LocalMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<VideoRead | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: async (selected: File) => {
      const form = new FormData();
      form.append("file", selected);
      const response = await fetch(`${API_BASE}/api/videos/upload`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiClientError(body.error_code ?? "UPLOAD_FAILED", body.message ?? "Upload failed", body.details ?? {});
      }
      return (await response.json()) as VideoRead;
    },
    onSuccess: (video) => {
      setUploaded(video);
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const processMutation = useMutation({
    mutationFn: (videoId: string) => apiPost<JobRead>(`/api/videos/${videoId}/process`, { processing_profile: "balanced" }),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      router.push(`/jobs/${job.id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  const accept = useMemo(() => ALLOWED.map((e) => `.${e}`).join(","), []);

  async function inspectFile(selected: File) {
    setError(null);
    setUploaded(null);
    const ext = selected.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED.includes(ext)) {
      setError(`Unsupported extension .${ext}. Allowed: ${ALLOWED.join(", ").toUpperCase()}`);
      setFile(null);
      setMeta(null);
      return;
    }
    setFile(selected);
    const local: LocalMeta = { name: selected.name, size: selected.size, type: selected.type || "unknown" };
    try {
      const url = URL.createObjectURL(selected);
      const video = document.createElement("video");
      video.preload = "metadata";
      await new Promise<void>((resolve, reject) => {
        video.onloadedmetadata = () => resolve();
        video.onerror = () => reject(new Error("Browser could not read video metadata"));
        video.src = url;
      });
      local.duration = video.duration;
      local.width = video.videoWidth;
      local.height = video.videoHeight;
      URL.revokeObjectURL(url);
    } catch {
      /* Server will still validate with OpenCV */
    }
    setMeta(local);
  }

  return (
    <section className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-xl font-medium">Upload footage</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Submit roadside or CCTV video for vehicle tracking and Indian plate recognition.
        </p>
        <p className="mt-1 text-sm text-[var(--muted)]">Supported formats: MP4, AVI, MOV, MKV, WEBM</p>
      </div>

      <Card>
        <div
          role="button"
          tabIndex={0}
          aria-label="Video upload drop zone"
          className={`flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-sm border border-dashed px-4 py-10 text-center ${
            dragOver ? "border-[var(--accent)] bg-[var(--hover)]" : "border-[var(--border)] bg-[var(--panel)]"
          }`}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const dropped = e.dataTransfer.files?.[0];
            if (dropped) void inspectFile(dropped);
          }}
        >
          <p className="text-sm font-medium">Drag and drop your video here</p>
          <p className="mt-2 text-sm text-[var(--muted)]">or</p>
          <p className="mt-2 text-sm text-[var(--accent)]">Browse files</p>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => {
              const selected = e.target.files?.[0];
              if (selected) void inspectFile(selected);
            }}
          />
        </div>

        {meta && (
          <div className="mt-4 grid gap-2 border-t border-[var(--border)] pt-4 text-sm md:grid-cols-2">
            <p>Filename: {meta.name}</p>
            <p>File size: {formatBytes(meta.size)}</p>
            <p>Duration: {meta.duration != null ? `${meta.duration.toFixed(1)}s` : "— (server will probe)"}</p>
            <p>
              Resolution:{" "}
              {meta.width && meta.height ? `${meta.width}×${meta.height}` : "— (server will probe)"}
            </p>
            <p>MIME: {meta.type}</p>
            <p>FPS / Codec: extracted after upload</p>
          </div>
        )}

        {error && <p className="mt-4 text-sm text-[#c45c5c]" role="alert">{error}</p>}

        {uploaded && (
          <div className="mt-4 rounded-sm border border-[#2a5540] bg-[#132018] p-3 text-sm">
            <p className="font-medium text-[#3d9a6a]">Upload complete</p>
            <p className="mt-1 text-[var(--muted)]">
              {uploaded.width}×{uploaded.height} · {uploaded.fps?.toFixed?.(1) ?? "—"} FPS · {uploaded.codec ?? "codec unknown"} ·{" "}
              {uploaded.frame_count ?? "—"} frames
            </p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={!file || uploadMutation.isPending || !!uploaded}
            onClick={() => file && uploadMutation.mutate(file)}
          >
            {uploadMutation.isPending ? "Uploading…" : "Upload"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={!uploaded || processMutation.isPending}
            onClick={() => uploaded && processMutation.mutate(uploaded.id)}
          >
            {processMutation.isPending ? "Starting…" : "Create processing job"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setFile(null);
              setMeta(null);
              setUploaded(null);
              setError(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            Remove
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.push("/videos")}>
            Cancel
          </Button>
        </div>
      </Card>
    </section>
  );
}
