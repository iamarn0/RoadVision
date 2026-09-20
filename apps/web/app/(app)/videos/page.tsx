"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, formatBytes, formatSeconds, type JobRead, type VideoRead } from "@/lib/api";
import { statusLabel, statusTone } from "@/lib/status";
import { Button, Card, EmptyState, Skeleton } from "@/components/ui";

export default function VideosPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const videos = useQuery({
    queryKey: ["videos"],
    queryFn: () => apiGet<VideoRead[]>("/api/videos"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/videos/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["videos"] }),
  });
  const process = useMutation({
    mutationFn: (id: string) => apiPost<JobRead>(`/api/videos/${id}/process`, { processing_profile: "balanced" }),
    onSuccess: (job) => router.push(`/jobs/${job.id}`),
  });

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-medium">Videos</h1>
          <p className="mt-1 text-sm text-[#9aa8b5]">Uploaded roadside and CCTV footage awaiting or completing ANPR.</p>
        </div>
        <Link href="/videos/upload" className="rounded-sm bg-[#2f9e9e] px-3 py-2 text-sm text-[#0f1419]">
          Upload footage
        </Link>
      </div>
      {videos.isLoading && <Skeleton className="h-40" />}
      {videos.isError && <p className="text-sm text-[#c45c5c]">Unable to load videos.</p>}
      {videos.data && videos.data.length === 0 && (
        <EmptyState
          title="No footage uploaded yet"
          description="Upload roadside or CCTV video files to begin plate recognition."
        />
      )}
      {videos.data && videos.data.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[#2a3441] text-xs uppercase tracking-wide text-[#9aa8b5]">
              <tr>
                <th className="px-4 py-3">Filename</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Resolution</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {videos.data.map((video) => (
                <tr key={video.id} className="border-b border-[#2a3441]">
                  <td className="px-4 py-3">{video.original_filename}</td>
                  <td className="px-4 py-3">{formatBytes(video.file_size)}</td>
                  <td className="px-4 py-3">
                    {video.width && video.height ? `${video.width}x${video.height}` : "-"}
                  </td>
                  <td className="px-4 py-3">{formatSeconds(video.duration)}</td>
                  <td className={`px-4 py-3 ${statusTone(video.status)}`}>{statusLabel(video.status)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <Button type="button" onClick={() => process.mutate(video.id)}>
                        Process
                      </Button>
                      <Button
                        type="button"
                        variant="danger"
                        onClick={() => {
                          if (confirm("Delete this video?")) remove.mutate(video.id);
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </section>
  );
}
