import { describe, expect, it } from "vitest";

const ALLOWED = ["mp4", "avi", "mov", "mkv", "webm"];

function validateClientExtension(filename: string): boolean {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return ALLOWED.includes(ext);
}

describe("upload client validation", () => {
  it("accepts mp4", () => {
    expect(validateClientExtension("road.mp4")).toBe(true);
  });

  it("rejects txt", () => {
    expect(validateClientExtension("notes.txt")).toBe(false);
  });
});
