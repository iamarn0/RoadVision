"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiGet, type JobRead } from "@/lib/api";
import { statusLabel, statusTone } from "@/lib/status";
import { Card, EmptyState, Skeleton } from "@/components/ui";

export default function JobsPage() {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiGet<JobRead[]>("/api/jobs"),
    refetchInterval: 3000,
  });

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-xl font-medium">Processing</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">ANPR jobs running on uploaded footage.</p>
      </div>
      {jobs.isLoading && <Skeleton className="h-40" />}
      {jobs.isError && <p className="text-sm text-[#c45c5c]">Unable to load jobs.</p>}
      {jobs.data && jobs.data.length === 0 && (
        <EmptyState
          title="No processing jobs yet"
          description="Upload footage and start a processing job to detect vehicles and plates."
        />
      )}
      {jobs.data && jobs.data.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Video</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3">FPS</th>
                <th className="px-4 py-3">Device</th>
                <th className="px-4 py-3">Plates</th>
              </tr>
            </thead>
            <tbody>
              {jobs.data.map((job) => (
                <tr key={job.id} className="border-b border-[var(--border)]">
                  <td className="px-4 py-3">
                    <Link href={`/jobs/${job.id}`} className="text-[var(--accent)] hover:underline">
                      {job.source_filename ?? job.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className={`px-4 py-3 ${statusTone(job.status)}`}>{statusLabel(job.status)}</td>
                  <td className="px-4 py-3">{job.progress.toFixed(1)}%</td>
                  <td className="px-4 py-3">{job.processing_fps?.toFixed(1) ?? "—"}</td>
                  <td className="px-4 py-3">{job.gpu_name ?? job.actual_device ?? "—"}</td>
                  <td className="px-4 py-3">{job.plates_detected}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </section>
  );
}
