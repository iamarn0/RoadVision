export function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

export function statusTone(status: string): string {
  switch (status) {
    case "completed":
    case "ready":
    case "healthy":
    case "high_confidence":
    case "configured":
      return "text-[#3d9a6a]";
    case "processing":
    case "validating":
    case "finalizing":
    case "queued":
    case "paused":
    case "medium_confidence":
    case "warning":
      return "text-[#c9922a]";
    case "failed":
    case "cancelled":
    case "critical":
    case "low_confidence":
    case "uncertain":
    case "needs_verification":
    case "not_configured":
      return "text-[#c45c5c]";
    default:
      return "text-[#9aa8b5]";
  }
}
