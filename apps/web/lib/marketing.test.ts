import { describe, expect, it } from "vitest";
import { resolveMarketingFile } from "./marketing";
import { validateContact } from "./contact";

describe("marketing routes", () => {
  it("maps primary pages to static html", () => {
    expect(resolveMarketingFile("/")).toBe("/home/index.html");
    expect(resolveMarketingFile("/about")).toBe("/home/about.html");
    expect(resolveMarketingFile("/services")).toBe("/home/services.html");
    expect(resolveMarketingFile("/projects")).toBe("/home/projects.html");
    expect(resolveMarketingFile("/contact")).toBe("/home/contact.html");
  });

  it("maps known service and project slugs", () => {
    expect(resolveMarketingFile("/services/anpr-recognition")).toBe("/home/service-detail.html");
    expect(resolveMarketingFile("/projects/highway-corridor")).toBe("/home/project-detail.html");
  });

  it("keeps unknown slugs on the public 404 page", () => {
    expect(resolveMarketingFile("/services/unknown")).toBe("/home/not-found.html");
    expect(resolveMarketingFile("/login")).toBeNull();
  });
});

describe("contact validation", () => {
  it("accepts a complete enquiry", () => {
    const result = validateContact({
      name: "Priya Sen",
      email: "priya@example.com",
      phone: "9831933297",
      service: "anpr-recognition",
      message: "We need ANPR at two parking gates in Kolkata.",
    });
    expect(result.ok).toBe(true);
  });

  it("rejects a short message", () => {
    const result = validateContact({
      name: "Priya Sen",
      email: "priya@example.com",
      phone: "9831933297",
      service: "anpr-recognition",
      message: "Hi",
    });
    expect(result.ok).toBe(false);
  });
});
