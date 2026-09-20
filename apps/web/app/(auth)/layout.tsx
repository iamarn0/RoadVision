import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <div className="flex min-h-screen items-center justify-center bg-[#0b0f14] p-6">{children}</div>;
}
