import { Suspense } from "react";
import { AuthForm } from "@/components/landing/auth-form";

export const metadata = { title: "Create account · Repurpora" };

export default function SignupPage() {
  return (
    <Suspense>
      <AuthForm mode="signup" />
    </Suspense>
  );
}
