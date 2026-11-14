"use client";

import { useRef, useState } from "react";
import { FileUp, LogOut, LoaderCircle, Home } from "lucide-react";
import { toast } from "sonner";
import { authHeaders, useAuth } from "@/providers/Auth";
import { Button } from "../ui/button";

export const SAMPLE_PROMPTS = [
  {
    title: "Full repurposing assessment",
    prompt:
      "Assess montelukast for repurposing in India: unmet needs, ongoing clinical trials, new indications, patents and an innovative product story.",
  },
  {
    title: "Low competition, high burden",
    prompt: "Which respiratory diseases show low competition but high patient burden in India?",
  },
  {
    title: "Patent & FTO check",
    prompt: "Check the patent landscape and freedom-to-operate risk for colchicine in cardiovascular secondary prevention.",
  },
  {
    title: "My saved reports",
    prompt: "List my saved reports with their decisions and ML scores",
  },
  {
    title: "Your research memory",
    prompt: "What do you remember about my research so far?",
  },
  {
    title: "Dosage-form innovation",
    prompt: "Is there an innovative dosage-form opportunity for budesonide in eosinophilic esophagitis in India?",
  },
];

const MOCK_API = process.env.NEXT_PUBLIC_MOCK_API_URL || "http://localhost:8081";

export function ChatToolbar() {
  const { session, signOut } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const email = session?.user?.email ?? "";

  const upload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF files are supported");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${MOCK_API}/documents/upload`, { method: "POST", body: fd, headers: authHeaders(session) });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || r.statusText);
      toast.success(`Indexed ${file.name}`, {
        description: `${body.chunks} chunks added to your private internal-knowledge index.`,
      });
    } catch (e) {
      toast.error("Upload failed", { description: String((e as Error).message) });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="flex items-center gap-1">
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <Button
        variant="ghost"
        size="sm"
        title="Upload an internal PDF for the Internal Knowledge agent"
        aria-label="Upload an internal PDF"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? <LoaderCircle className="size-4 animate-spin" /> : <FileUp className="size-4" />}
        <span className="hidden md:inline">Upload PDF</span>
      </Button>
      <a href="/" title="Home" aria-label="Home" className="p-2 rounded-md hover:bg-gray-100">
        <Home className="size-4" />
      </a>
      {email && (
        <span className="hidden md:inline text-xs text-muted-foreground max-w-40 truncate" title={email}>
          {email}
        </span>
      )}
      <Button variant="ghost" size="sm" onClick={signOut} title="Sign out" aria-label="Sign out" data-testid="sign-out">
        <LogOut className="size-4" />
      </Button>
    </div>
  );
}
