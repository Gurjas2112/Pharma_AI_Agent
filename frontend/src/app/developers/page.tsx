"use client";

import { AuthProvider } from "@/providers/Auth";
import { Toaster } from "@/components/ui/sonner";
import { McpConsole } from "@/components/developers/mcp-console";

export default function DevelopersPage() {
  return (
    <AuthProvider>
      <Toaster />
      <McpConsole />
    </AuthProvider>
  );
}
