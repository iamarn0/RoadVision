"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { apiGet, type JobRead, type VideoRead } from "@/lib/api";
import { statusLabel, statusTone } from "@/lib/status";
import { Card, EmptyState, Skeleton } from "@/components/ui";

type DashboardMetrics = {
  videos_processed: number;
  processing_jobs: number;
  vehicles_detected: number;
  unique_plates: number;
  active_jobs: JobRead[];
  recent_videos: VideoRead[];
};

export default function DashboardPage() {
  const metrics = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiGet<DashboardMetrics>("/api/dashboard"),
    refetchInterval: 5000,
  });

  if (metrics.isLoading) {
    return (
      <section className="space-y-4">
        <h1 className="text-xl font-medium">Overview</h1>
        <div className="grid gap-3 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </section>
    );
  }

  if (metrics.isError || !metrics.data) {
    return (
      <section>
        <h1 className="text-xl font-medium">Overview</h1>
        <p className="mt-2 text-[#c45c5c]">Unable to load dashboard metrics. Is the API running?</p>
      </section>
    );
  }

  const data = metrics.data;
  const empty =
    data.videos_processed === 0 &&
    data.processing_jobs === 0 &&
    data.vehicles_detected === 0 &&
    data.unique_plates === 0;

  return (
    <section className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-medium">Overview</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Live ANPR operations summary from processed CCTV and roadside footage.
          </p>
        </div>
        <Link href="/videos" className="rounded-sm bg-[var(--accent)] px-3 py-2 text-sm text-white">
          Upload footage
        </Link>
      </div>

      {empty ? (
        <EmptyState
          title="No operations data yet"
          description="Upload roadside or CCTV video to begin vehicle and number plate recognition."
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-4">
          {[
            ["Videos Processed", data.videos_processed],
            ["Processing Jobs", data.processing_jobs],
            ["Vehicles Detected", data.vehicles_detected],
            ["Unique Plates", data.unique_plates],
          ].map(([label, value]) => (
            <Card key={String(label)}>
              <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</p>
              <p className="mt-2 text-2xl font-medium">{value}</p>
            </Card>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-medium">Active Processing Jobs</h2>
          {data.active_jobs.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--muted)]">No active jobs.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {data.active_jobs.map((job) => (
                <li key={job.id} className="flex items-center justify-between text-sm">
                  <Link href={`/jobs/${job.id}`} className="text-[var(--accent)] hover:underline">
                    {job.source_filename ?? job.id.slice(0, 8)}
                  </Link>
                  <span className={statusTone(job.status)}>
                    {statusLabel(job.status)} · {job.progress.toFixed(0)}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-medium">Recent Videos</h2>
          {data.recent_videos.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--muted)]">No footage uploaded yet.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {data.recent_videos.map((video) => (
                <li key={video.id} className="flex justify-between gap-3">
                  <span className="truncate">{video.original_filename}</span>
                  <span className="text-[var(--muted)]">
                    {video.width && video.height ? `${video.width}×${video.height}` : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </section>
  );
}
