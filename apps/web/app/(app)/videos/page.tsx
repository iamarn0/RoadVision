"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, formatBytes, formatSeconds, type JobRead, type VideoRead } from "@/lib/api";
import { canDeleteVideos, canUpload } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";
import { statusLabel, statusTone } from "@/lib/status";
import { Button, Card, EmptyState, Modal, Skeleton } from "@/components/ui";
import { VideoUploadForm } from "@/components/video-upload-form";

export default function VideosPage() {
  const router = useRouter();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const allowProcess = canUpload(user?.role);
  const allowDelete = canDeleteVideos(user?.role);
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
          <p className="mt-1 text-sm text-[var(--muted)]">Uploaded roadside and CCTV footage awaiting or completing ANPR.</p>
        </div>
        {allowProcess && (
          <Button type="button" onClick={() => setUploadOpen(true)}>
            Upload footage
          </Button>
        )}
      </div>
      {videos.isLoading && <Skeleton className="h-40" />}
      {videos.isError && <p className="text-sm text-[#c45c5c]">Unable to load videos.</p>}
      {remove.isError && (
        <p className="text-sm text-[#c45c5c]">{remove.error instanceof Error ? remove.error.message : "Unable to delete video."}</p>
      )}
      {process.isError && (
        <p className="text-sm text-[#c45c5c]">{process.error instanceof Error ? process.error.message : "Unable to start processing."}</p>
      )}
      {videos.data && videos.data.length === 0 && (
        <EmptyState
          title="No footage uploaded yet"
          description="Upload roadside or CCTV video files to begin plate recognition."
        />
      )}
      {videos.data && videos.data.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-xs uppercase tracking-wide text-[var(--muted)]">
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
                <tr key={video.id} className="border-b border-[var(--border)]">
                  <td className="px-4 py-3">{video.original_filename}</td>
                  <td className="px-4 py-3">{formatBytes(video.file_size)}</td>
                  <td className="px-4 py-3">
                    {video.width && video.height ? `${video.width}x${video.height}` : "-"}
                  </td>
                  <td className="px-4 py-3">{formatSeconds(video.duration)}</td>
                  <td className={`px-4 py-3 ${statusTone(video.status)}`}>{statusLabel(video.status)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      {allowProcess && (
                        <Button type="button" onClick={() => process.mutate(video.id)} disabled={process.isPending}>
                          Process
                        </Button>
                      )}
                      {allowDelete && (
                        <Button
                          type="button"
                          variant="danger"
                          disabled={remove.isPending}
                          onClick={() => {
                            if (confirm("Delete this video and its processing jobs?")) remove.mutate(video.id);
                          }}
                        >
                          {remove.isPending ? "Deleting…" : "Delete"}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <Modal open={uploadOpen} title="Upload footage" size="lg" onClose={() => setUploadOpen(false)}>
        {uploadOpen && <VideoUploadForm key={String(uploadOpen)} onCancel={() => setUploadOpen(false)} />}
      </Modal>
    </section>
  );
}
