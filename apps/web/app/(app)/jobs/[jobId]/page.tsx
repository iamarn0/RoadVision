"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  API_BASE,
  ApiClientError,
  apiGet,
  apiPost,
  formatSeconds,
  mediaUrl,
  type CaptureJobResponse,
  type JobRead,
  type LiveCaptureItem,
  type LiveCapturesResponse,
} from "@/lib/api";
import { statusLabel, statusTone } from "@/lib/status";
import { Badge, Button, Card, EmptyState, Modal, Skeleton } from "@/components/ui";

function isSnapshot(item: LiveCaptureItem) {
  return item.kind === "snapshot" || (item.plate_url?.includes("/snapshots/") ?? false);
}

function isVehicleOnly(item: LiveCaptureItem) {
  return item.kind === "vehicle";
}

function captureSrc(item: LiveCaptureItem, kind: "plate" | "vehicle" | "full" = "plate") {
  const path =
    kind === "full" ? item.full_url || item.vehicle_url || item.plate_url : kind === "vehicle" ? item.vehicle_url : item.plate_url;
  return `${API_BASE}${path}?t=${Math.floor(item.updated_at * 1000)}`;
}

function captureTimeValue(item: LiveCaptureItem) {
  if (item.first_seen_seconds != null) return item.first_seen_seconds;
  if (item.timestamp != null) return item.timestamp;
  return item.updated_at || 0;
}

function captureTimeLabel(item: LiveCaptureItem) {
  if (item.timestamp_overlay) return item.timestamp_overlay;
  return "—";
}

function formatConfidence(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function CapturesTable({
  items,
  sort,
  compact,
  onOpen,
}: {
  items: LiveCaptureItem[];
  sort: "newest" | "oldest";
  compact?: boolean;
  onOpen: (item: LiveCaptureItem) => void;
}) {
  const rows = [...items].sort((a, b) => {
    const delta = captureTimeValue(b) - captureTimeValue(a);
    return sort === "oldest" ? -delta : delta;
  });
  if (!rows.length) {
    return (
      <EmptyState
        title="No captures yet"
        description="Plate rows appear here as soon as a capture has enough information. Capture saves the current frame as a snapshot row."
      />
    );
  }
  return (
    <div className={compact ? "max-h-[70vh] overflow-auto" : "overflow-x-auto"}>
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 border-b border-[var(--border)] bg-[var(--panel)] text-xs uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="px-2 py-2">Plate</th>
            <th className="px-2 py-2">Vehicle</th>
            <th className="px-2 py-2">Type</th>
            <th className="px-2 py-2">Track</th>
            <th className="px-2 py-2">Timestamp</th>
            <th className="px-2 py-2">Details</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((cap) => (
            <tr key={`${cap.kind ?? "plate"}-${cap.track_id}-${cap.updated_at}`} className="border-b border-[var(--border)]">
              <td className="px-2 py-2">
                {isVehicleOnly(cap) ? (
                  <span className="text-[var(--muted)]">No plate</span>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={captureSrc(cap, "plate")}
                    alt={isSnapshot(cap) ? "Snapshot" : `Plate ${cap.track_id}`}
                    className="h-10 w-20 bg-black object-contain"
                  />
                )}
              </td>
              <td className="px-2 py-2">
                {isSnapshot(cap) ? (
                  <span className="text-[var(--muted)]">Full frame</span>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={captureSrc(cap, "vehicle")} alt={`Vehicle ${cap.track_id}`} className="h-10 w-20 bg-black object-contain" />
                )}
              </td>
              <td className="px-2 py-2">
                {isSnapshot(cap) ? "Snapshot" : cap.vehicle_type || "—"}
                {isVehicleOnly(cap) ? (
                  <span className="mt-1 block text-xs text-[var(--muted)]">No plate</span>
                ) : cap.good_evidence === false ? (
                  <span className="mt-1 block text-xs text-[#c45c5c]">Low detail</span>
                ) : null}
              </td>
              <td className="px-2 py-2">{isSnapshot(cap) ? `S#${cap.track_id}` : `#${cap.track_id}`}</td>
              <td className="whitespace-nowrap px-2 py-2">{captureTimeLabel(cap)}</td>
              <td className="px-2 py-2">
                <Button type="button" variant="ghost" onClick={() => onOpen(cap)}>
                  View
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [liveTick, setLiveTick] = useState(0);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [controlError, setControlError] = useState<string | null>(null);
  const [previewPaused, setPreviewPaused] = useState(false);
  const [previewCap, setPreviewCap] = useState<LiveCaptureItem | null>(null);
  const heldFrameUrlRef = useRef<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const framePaceRef = useRef<{ frame: number; at: number } | null>(null);
  const resumeAtRef = useRef<number | null>(null);
  const queryClient = useQueryClient();

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => apiGet<JobRead>(`/api/jobs/${jobId}`),
    refetchInterval: (query) => {
      const statusValue = query.state.data?.status;
      return statusValue && ["queued", "validating", "processing", "finalizing"].includes(statusValue)
        ? 400
        : false;
    },
  });

  const active =
    !!job.data && ["queued", "validating", "processing", "finalizing"].includes(job.data.status);

  const paused = previewPaused || !!job.data?.paused;

  const liveCaptures = useQuery({
    queryKey: ["live-captures", jobId],
    queryFn: () => apiGet<LiveCapturesResponse>(`/api/jobs/${jobId}/live-captures`),
    enabled: active || job.data?.status === "completed" || job.data?.status === "cancelled",
    refetchInterval: active ? (paused ? 800 : 600) : false,
  });

  // Polling stops once the job leaves the live states. Refetch so vehicles
  // still in frame on the last second are included after they are published.
  useEffect(() => {
    const status = job.data?.status;
    if (status !== "completed" && status !== "cancelled" && status !== "finalizing") return;
    void queryClient.invalidateQueries({ queryKey: ["live-captures", jobId] });
  }, [job.data?.status, jobId, queryClient]);

  const liveReady = !!job.data?.live_frame_available;

  useEffect(() => {
    if (!active || paused || !liveReady) return;
    const id = window.setInterval(() => setLiveTick((t) => t + 1), 120);
    return () => window.clearInterval(id);
  }, [active, paused, liveReady]);

  // Stay on the frame being processed. A 100 fps file must not race ahead and then jump back.
  useEffect(() => {
    const el = videoRef.current;
    const j = job.data;
    if (!el || !j || !active) return;
    const fps = j.source_fps && j.source_fps > 0 ? j.source_fps : 25;
    const frame = j.current_frame || 0;
    const target = Math.max(0, frame / fps);
    if (paused || j.status !== "processing") {
      el.playbackRate = 1;
      framePaceRef.current = null;
      if (paused && target > 0.05) {
        resumeAtRef.current = Math.max(resumeAtRef.current || 0, target);
        if (Math.abs(el.currentTime - target) > 0.2) {
          try {
            el.currentTime = target;
          } catch {
            /* metadata may still be loading */
          }
        }
      }
      if (!el.paused) el.pause();
      return;
    }
    const resumeAt = resumeAtRef.current;
    if (resumeAt != null && resumeAt > 0.05) {
      resumeAtRef.current = null;
      framePaceRef.current = { frame, at: performance.now() };
      const continueAt = Math.max(resumeAt, target);
      const startPlayback = () => {
        if (videoRef.current?.paused) void videoRef.current.play().catch(() => undefined);
      };
      if (Math.abs(el.currentTime - continueAt) > 0.15) {
        const onSeeked = () => {
          el.removeEventListener("seeked", onSeeked);
          startPlayback();
        };
        el.addEventListener("seeked", onSeeked);
        try {
          el.currentTime = continueAt;
        } catch {
          el.removeEventListener("seeked", onSeeked);
          startPlayback();
        }
      } else {
        startPlayback();
      }
      return;
    }
    if (frame < 2) {
      el.playbackRate = 1;
      if (!el.paused) el.pause();
      return;
    }
    const now = performance.now();
    const prev = framePaceRef.current;
    let rate = 1;
    if (prev && frame > prev.frame) {
      const framesPerSec = (frame - prev.frame) / Math.max(0.05, (now - prev.at) / 1000);
      rate = Math.min(1, Math.max(0.25, framesPerSec / fps));
    }
    framePaceRef.current = { frame, at: now };
    const drift = el.currentTime - target;
    // Rewinding to the processed frame repeats the same picture. Wait in place instead.
    if (drift > 0.45) {
      el.playbackRate = 1;
      if (!el.paused) el.pause();
      return;
    }
    el.playbackRate = drift > 0.12 ? Math.min(rate, 0.5) : rate;
    if (drift < -1) {
      try {
        el.currentTime = target;
      } catch {
        /* ignore seek errors while metadata loads */
      }
    }
    if (el.paused) void el.play().catch(() => undefined);
  }, [active, paused, job.data?.current_frame, job.data?.source_fps, job.data?.status]);

  const cancel = useMutation({
    mutationFn: () => apiPost<JobRead>(`/api/jobs/${jobId}/cancel`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job", jobId] }),
  });
  const pause = useMutation({
    mutationFn: () => apiPost<JobRead>(`/api/jobs/${jobId}/pause`),
    onMutate: () => {
      setControlError(null);
      const fps = job.data?.source_fps && job.data.source_fps > 0 ? job.data.source_fps : 25;
      const el = videoRef.current;
      const fromVideo = el?.currentTime || 0;
      const fromJob = Math.max(0, (job.data?.current_frame || 0) / fps);
      const at = Math.max(fromVideo, fromJob);
      resumeAtRef.current = at;
      if (el) {
        el.pause();
        if (at > 0.05) {
          try {
            el.currentTime = at;
          } catch {
            /* metadata may still be loading */
          }
        }
      }
      heldFrameUrlRef.current = `${API_BASE}/api/jobs/${jobId}/live-frame?t=${job.data?.current_frame ?? 0}-${liveTick}`;
      setPreviewPaused(true);
    },
    onSuccess: (data) => queryClient.setQueryData(["job", jobId], data),
    onError: (error) => {
      setPreviewPaused(false);
      heldFrameUrlRef.current = null;
      const message = error instanceof ApiClientError ? error.message : "Pause failed.";
      setControlError(message);
    },
  });
  const resume = useMutation({
    mutationFn: () => apiPost<JobRead>(`/api/jobs/${jobId}/resume`),
    onMutate: () => {
      setControlError(null);
      setPreviewPaused(false);
      heldFrameUrlRef.current = null;
    },
    onSuccess: (data) => queryClient.setQueryData(["job", jobId], data),
    onError: (error) => {
      setPreviewPaused(true);
      const message = error instanceof ApiClientError ? error.message : "Play failed.";
      setControlError(message);
    },
  });
  const capture = useMutation({
    mutationFn: () => apiPost<CaptureJobResponse>(`/api/jobs/${jobId}/capture`),
    onMutate: () => setCaptureError(null),
    onSuccess: (data) => {
      if (data.snapshot) {
        queryClient.setQueryData<LiveCapturesResponse>(["live-captures", jobId], (current) => {
          const items = current?.items ?? [];
          const next = [
            data.snapshot as LiveCaptureItem,
            ...items.filter((item) => !(isSnapshot(item) && item.track_id === data.snapshot?.track_id)),
          ];
          return { job_id: jobId, plates_captured: next.length, items: next };
        });
        setPreviewCap(data.snapshot);
      }
      void queryClient.invalidateQueries({ queryKey: ["live-captures", jobId] }).then(() => {
        if (data.snapshot) return;
        const latest = queryClient.getQueryData<LiveCapturesResponse>(["live-captures", jobId]);
        const newest = latest?.items.find(isSnapshot);
        if (newest) setPreviewCap(newest);
      });
    },
    onError: (error) => {
      const message = error instanceof ApiClientError ? error.message : "Capture failed.";
      setCaptureError(message);
    },
  });
  const retry = useMutation({
    mutationFn: () => apiPost<JobRead>(`/api/jobs/${jobId}/retry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job", jobId] }),
  });
  const exportMutation = useMutation({
    mutationFn: async (type: string) => {
      const exp = await apiPost<{ id: string; media_asset_id?: string }>(`/api/jobs/${jobId}/exports/${type}`);
      if (exp.media_asset_id) {
        window.open(`${API_BASE}/api/media/${exp.media_asset_id}`, "_blank");
      }
      return exp;
    },
  });

  const annotated = useMemo(() => mediaUrl(job.data?.annotated_asset_id), [job.data?.annotated_asset_id]);
  const originalVideo = useMemo(() => mediaUrl(job.data?.original_asset_id), [job.data?.original_asset_id]);
  const liveFrameUrl = useMemo(() => {
    if (paused && heldFrameUrlRef.current) return heldFrameUrlRef.current;
    if (!liveReady) return null;
    return `${API_BASE}/api/jobs/${jobId}/live-frame?t=${job.data?.current_frame ?? 0}-${liveTick}`;
  }, [paused, liveReady, jobId, job.data?.current_frame, liveTick]);

  useEffect(() => {
    if (!active) {
      setPreviewPaused(false);
      heldFrameUrlRef.current = null;
    }
  }, [active]);

  if (job.isLoading) return <Skeleton className="h-64" />;
  if (job.isError || !job.data) return <p className="text-[#c45c5c]">Job not found.</p>;

  const j = job.data;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-medium">Live Detection</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">{j.source_filename ?? j.id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {active && (
            <Button type="button" variant="danger" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
              Cancel
            </Button>
          )}
          {(j.status === "failed" || j.status === "cancelled") && (
            <Button type="button" onClick={() => retry.mutate()} disabled={retry.isPending}>
              Retry
            </Button>
          )}
          {j.status === "completed" && (
            <>
              <Button type="button" variant="ghost" onClick={() => exportMutation.mutate("csv")}>
                Export CSV
              </Button>
              <Button type="button" variant="ghost" onClick={() => exportMutation.mutate("xlsx")}>
                Export XLSX
              </Button>
              <Button type="button" variant="ghost" onClick={() => exportMutation.mutate("json")}>
                Export JSON
              </Button>
              <Button type="button" variant="ghost" onClick={() => exportMutation.mutate("evidence-zip")}>
                Evidence ZIP
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Card>
          <p className="text-xs uppercase text-[var(--muted)]">Rendered FPS</p>
          <p className="mt-2 text-2xl">100</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-[var(--muted)]">Plates Captured</p>
          <p className="mt-2 text-2xl">
            {liveCaptures.data?.plates_captured ?? j.plates_detected}
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-[var(--muted)]">Source FPS</p>
          <p className="mt-2 text-2xl">{j.source_fps?.toFixed(1) ?? "—"}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-[var(--muted)]">Status</p>
          <p className={`mt-2 text-lg ${statusTone(paused ? "paused" : j.status)}`}>
            {paused ? "paused" : statusLabel(j.status)}
          </p>
        </Card>
      </div>

      {(active || j.status === "queued") && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.9fr)]">
          <Card className="overflow-hidden p-0">
            <div className="border-b border-[var(--border)] px-4 py-3">
              <h2 className="text-sm font-medium">Realtime processing</h2>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Playback stays on the frame being processed. Pause to inspect a frame, then capture that picture.
              </p>
            </div>
            <div className="relative aspect-video bg-black">
              {originalVideo ? (
                <video
                  ref={videoRef}
                  className={
                    liveFrameUrl
                      ? "pointer-events-none absolute h-0 w-0 opacity-0"
                      : "h-full w-full object-contain"
                  }
                  src={originalVideo}
                  muted
                  playsInline
                >
                  <track kind="captions" />
                </video>
              ) : (
                <div className="flex h-full items-center justify-center px-6 text-center text-sm text-[var(--muted)]">
                  Waiting for first frame…
                </div>
              )}
              {liveFrameUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={liveFrameUrl}
                  alt="Live annotated frame"
                  className="h-full w-full object-contain"
                />
              )}
              {j.status === "validating" && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/75 px-6 text-center text-sm text-white">
                  Preparing this video so it can play and process on this system…
                </div>
              )}
              {paused && j.status === "processing" && (
                <div className="absolute left-3 top-3">
                  <Badge className="border-[#c9922a] bg-[#1a1610] text-[#c9922a]">Paused</Badge>
                </div>
              )}
            </div>
            <div className="space-y-3 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                {paused ? (
                  <Button
                    type="button"
                    onClick={() => resume.mutate()}
                    disabled={j.status !== "processing" || resume.isPending}
                  >
                    Play
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => pause.mutate()}
                    disabled={j.status !== "processing" || pause.isPending}
                  >
                    Pause
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => capture.mutate()}
                  disabled={j.status !== "processing" || capture.isPending}
                >
                  Capture
                </Button>
                {controlError && <p className="text-sm text-[#c45c5c]">{controlError}</p>}
                {captureError && <p className="text-sm text-[#c45c5c]">{captureError}</p>}
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-[var(--border)]">
                <div className="h-full bg-[var(--accent)]" style={{ width: `${Math.min(100, j.progress)}%` }} />
              </div>
              <div className="grid gap-2 text-sm md:grid-cols-3">
                <p>
                  Time: {formatSeconds(j.current_frame / Math.max(j.source_fps || 25, 1))} /{" "}
                  {formatSeconds(j.total_frames / Math.max(j.source_fps || 25, 1))}
                </p>
                <p>
                  Frame: {j.current_frame.toLocaleString()} / {j.total_frames.toLocaleString()}
                </p>
                <p>Detect FPS: {j.processing_fps?.toFixed(1) ?? "—"}</p>
                <p>Device: {j.gpu_name ?? j.actual_device ?? "—"}</p>
                <p className={statusTone(paused ? "paused" : j.status)}>
                  Status: {paused ? "paused" : statusLabel(j.status)}
                </p>
                <p>
                  Remaining:{" "}
                  {j.estimated_remaining_seconds != null ? formatSeconds(j.estimated_remaining_seconds) : "—"}
                </p>
              </div>
            </div>
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="text-sm font-medium">Captures</h2>
              <div className="flex items-center gap-2">
                <select
                  aria-label="Sort captures"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as "newest" | "oldest")}
                  className="rounded-sm border border-[var(--border)] bg-[var(--panel)] px-2 py-1 text-xs"
                >
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                </select>
                <Badge>{liveCaptures.data?.items?.length ?? 0}</Badge>
              </div>
            </div>
            <CapturesTable
              items={liveCaptures.data?.items ?? []}
              sort={sort}
              compact
              onOpen={setPreviewCap}
            />
          </Card>
        </div>
      )}

      {j.status === "failed" && (
        <Card className="border-[#5a3030]">
          <h2 className="text-sm font-medium text-[#c45c5c]">Processing failed</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm">{j.error_message ?? "Unknown error"}</p>
          {j.error_code && <p className="mt-2 text-xs text-[var(--muted)]">Error code: {j.error_code}</p>}
        </Card>
      )}

      {j.status === "completed" && (
        <>
          <Card>
            <h2 className="mb-3 text-sm font-medium">Annotated video</h2>
            {annotated ? (
              <video controls className="max-h-[480px] w-full bg-black" src={annotated}>
                <track kind="captions" />
              </video>
            ) : (
              <p className="text-sm text-[var(--muted)]">Annotated video is not available.</p>
            )}
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="text-sm font-medium">Captures</h2>
              <div className="flex items-center gap-2">
                <select
                  aria-label="Sort captures"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as "newest" | "oldest")}
                  className="rounded-sm border border-[var(--border)] bg-[var(--panel)] px-2 py-1 text-xs"
                >
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                </select>
                <Badge>{liveCaptures.data?.items?.length ?? 0}</Badge>
              </div>
            </div>
            <CapturesTable items={liveCaptures.data?.items ?? []} sort={sort} onOpen={setPreviewCap} />
          </Card>
        </>
      )}

      <Modal
        open={!!previewCap}
        size="xl"
        title={previewCap?.label ?? (previewCap ? `Track #${previewCap.track_id}` : "Capture")}
        onClose={() => setPreviewCap(null)}
      >
        {previewCap ? (
          <div className="space-y-4">
            <div className="grid gap-2 text-sm md:grid-cols-2">
              <p>
                <span className="text-[var(--muted)]">Status: </span>
                {isSnapshot(previewCap) ? "Snapshot" : isVehicleOnly(previewCap) ? "No plate" : previewCap.good_evidence === false ? "Low detail" : "Captured"}
              </p>
              <p>
                <span className="text-[var(--muted)]">Confidence: </span>
                {isSnapshot(previewCap) ? "—" : formatConfidence(previewCap.plate_confidence)}
              </p>
              <p>
                <span className="text-[var(--muted)]">Type: </span>
                {isSnapshot(previewCap) ? "Snapshot" : previewCap.vehicle_type || "—"}
              </p>
              <p>
                <span className="text-[var(--muted)]">Track: </span>
                {isSnapshot(previewCap) ? `S#${previewCap.track_id}` : `#${previewCap.track_id}`}
              </p>
              <p className="md:col-span-2">
                <span className="text-[var(--muted)]">Seen: </span>
                {captureTimeLabel(previewCap)}
              </p>
              {previewCap.good_evidence === false ? (
                <p className="md:col-span-2 text-sm text-[#c45c5c]">
                  Plate is {previewCap.plate_width ? `${Math.round(previewCap.plate_width)} px wide` : "under 75 px wide"}. Characters are not fully resolved.
                </p>
              ) : null}
            </div>
            {isSnapshot(previewCap) ? (
              <div>
                <p className="mb-2 text-xs uppercase text-[var(--muted)]">Full frame</p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={captureSrc(previewCap, "full")} alt="Manual snapshot" className="max-h-[70vh] w-full bg-black object-contain" />
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <p className="mb-2 text-xs uppercase text-[var(--muted)]">Full frame</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={captureSrc(previewCap, "full")}
                    alt="Full frame"
                    className="mx-auto max-h-[70vh] w-auto max-w-full bg-black object-contain"
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                    }}
                  />
                </div>
                <div>
                  <p className="mb-2 text-xs uppercase text-[var(--muted)]">Vehicle</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={captureSrc(previewCap, "vehicle")}
                    alt="Vehicle crop"
                    className="mx-auto max-h-[64vh] w-auto max-w-full bg-black object-contain"
                  />
                </div>
                {isVehicleOnly(previewCap) ? (
                  <div>
                    <p className="mb-2 text-xs uppercase text-[var(--muted)]">Plate</p>
                    <p className="text-sm text-[var(--muted)]">No plate was read before the video ended.</p>
                  </div>
                ) : (
                  <div>
                    <p className="mb-2 text-xs uppercase text-[var(--muted)]">Plate</p>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={captureSrc(previewCap, "plate")}
                      alt="Plate crop"
                      className="mx-auto max-h-[32vh] w-full max-w-full bg-black object-contain"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}
      </Modal>
    </section>
  );
}
