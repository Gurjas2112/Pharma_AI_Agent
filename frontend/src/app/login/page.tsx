import { Suspense } from "react";
import { AuthForm } from "@/components/landing/auth-form";

export const metadata = { title: "Sign in · Repurpora" };

export default function LoginPage() {
  return (
    <Suspense>
      <AuthForm mode="login" />
    </Suspense>
  );
}
