import { redirect } from "next/navigation";

/** Site entry is always Sign in — never password-change or the ops console. */
export default function HomePage() {
  redirect("/login");
}
