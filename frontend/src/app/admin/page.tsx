"use client";

import { AuthProvider } from "@/providers/Auth";
import { Toaster } from "@/components/ui/sonner";
import { AdminApp } from "@/components/admin/admin-app";

export default function AdminPage() {
  return (
    <AuthProvider>
      <Toaster />
      <AdminApp />
    </AuthProvider>
  );
}
