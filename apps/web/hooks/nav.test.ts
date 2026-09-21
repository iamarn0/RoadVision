import { describe, expect, it } from "vitest";
import { NAV_COUNT } from "../lib/nav";
import { formatBytes, formatSeconds } from "../lib/api";
import { statusTone } from "../lib/status";

describe("navigation contract", () => {
  it("keeps five primary destinations for admins", () => {
    expect(NAV_COUNT).toBe(5);
  });
});

describe("formatting helpers", () => {
  it("formats seconds", () => {
    expect(formatSeconds(83)).toBe("1:23");
  });

  it("formats bytes", () => {
    expect(formatBytes(2048)).toContain("KB");
  });
});

describe("status tones", () => {
  it("maps failed to danger tone", () => {
    expect(statusTone("failed")).toContain("c45c5c");
  });
});
