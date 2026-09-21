export const SERVICE_SLUGS = [
  "traffic-analysis",
  "anpr-recognition",
  "road-condition-ai",
  "highway-cctv-intel",
  "fleet-dashcam-survey",
] as const;

export const PROJECT_SLUGS = [
  "highway-corridor",
  "pavement-survey",
  "anpr-gate",
  "incident-alerts",
  "city-traffic",
  "fleet-dashcam",
] as const;

export const CONTACT_SERVICES = [
  { value: "traffic-analysis", label: "Traffic Analysis" },
  { value: "anpr-recognition", label: "ANPR Recognition" },
  { value: "road-condition-ai", label: "Road Condition AI" },
  { value: "highway-cctv-intel", label: "Highway CCTV Intel" },
  { value: "fleet-dashcam-survey", label: "Fleet Dashcam Survey" },
  { value: "networking", label: "Networking Infrastructure" },
  { value: "support", label: "24/7 Support" },
] as const;

const SERVICE_SET = new Set<string>(SERVICE_SLUGS);
const PROJECT_SET = new Set<string>(PROJECT_SLUGS);

export function resolveMarketingFile(pathname: string): string | null {
  if (pathname === "/" || pathname === "") return "/home/index.html";
  if (pathname === "/about") return "/home/about.html";
  if (pathname === "/services") return "/home/services.html";
  if (pathname === "/projects") return "/home/projects.html";
  if (pathname === "/contact") return "/home/contact.html";

  const serviceMatch = pathname.match(/^\/services\/([a-z0-9-]+)$/);
  if (serviceMatch) {
    return SERVICE_SET.has(serviceMatch[1]) ? "/home/service-detail.html" : "/home/not-found.html";
  }

  const projectMatch = pathname.match(/^\/projects\/([a-z0-9-]+)$/);
  if (projectMatch) {
    return PROJECT_SET.has(projectMatch[1]) ? "/home/project-detail.html" : "/home/not-found.html";
  }

  return null;
}
