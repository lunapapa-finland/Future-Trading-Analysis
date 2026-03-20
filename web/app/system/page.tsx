import { redirect } from "next/navigation";

export default function SystemRedirectPage() {
  redirect("/config");
}
