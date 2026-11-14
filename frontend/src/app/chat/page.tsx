"use client";

import React from "react";
import { Thread } from "@/components/thread";
import { StreamProvider } from "@/providers/Stream";
import { ThreadProvider } from "@/providers/Thread";
import { AuthProvider } from "@/providers/Auth";
import { Toaster } from "@/components/ui/sonner";

export default function ChatPage(): React.ReactNode {
  return (
    <React.Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <Toaster />
      <AuthProvider>
        <ThreadProvider>
          <StreamProvider>
            <Thread />
          </StreamProvider>
        </ThreadProvider>
      </AuthProvider>
    </React.Suspense>
  );
}
