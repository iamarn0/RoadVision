import { CONTACT_SERVICES } from "./marketing";

export type ContactPayload = {
  name: string;
  email: string;
  phone: string;
  service: string;
  message: string;
  type?: "inquiry" | "newsletter";
};

export type ContactValidation =
  | { ok: true; data: ContactPayload }
  | { ok: false; message: string };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SERVICE_VALUES = new Set<string>(CONTACT_SERVICES.map((item) => item.value));

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function validateContact(input: unknown): ContactValidation {
  if (!input || typeof input !== "object") {
    return { ok: false, message: "Please send a valid enquiry." };
  }

  const body = input as Record<string, unknown>;
  const type = body.type === "newsletter" ? "newsletter" : "inquiry";
  const email = asString(body.email).toLowerCase();

  if (!EMAIL_RE.test(email)) {
    return { ok: false, message: "Please enter a valid email address." };
  }

  if (type === "newsletter") {
    return {
      ok: true,
      data: {
        name: asString(body.name) || "Newsletter subscriber",
        email,
        phone: "",
        service: "newsletter",
        message: "Please add this address to RoadVision updates.",
        type,
      },
    };
  }

  const name = asString(body.name);
  const phone = asString(body.phone);
  const service = asString(body.service);
  const message = asString(body.message);

  if (name.length < 2) {
    return { ok: false, message: "Please enter your name." };
  }
  if (phone.length < 8) {
    return { ok: false, message: "Please enter a valid mobile number." };
  }
  if (!SERVICE_VALUES.has(service)) {
    return { ok: false, message: "Please choose a service." };
  }
  if (message.length < 10) {
    return { ok: false, message: "Please describe what you need in a bit more detail." };
  }

  return {
    ok: true,
    data: { name, email, phone, service, message, type },
  };
}
