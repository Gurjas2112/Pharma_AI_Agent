"use client";

import { validate } from "uuid";
import { Client, Thread } from "@langchain/langgraph-sdk";
import { createContext, useContext, ReactNode, useCallback, useState, Dispatch, SetStateAction } from "react";
import { authHeaders, useAuth } from "./Auth";

interface ThreadContextType {
  getThreads: () => Promise<Thread[]>;
  threads: Thread[];
  setThreads: Dispatch<SetStateAction<Thread[]>>;
  threadsLoading: boolean;
  setThreadsLoading: Dispatch<SetStateAction<boolean>>;
}

const ThreadContext = createContext<ThreadContextType | undefined>(undefined);
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2026";
const ASSISTANT_ID = process.env.NEXT_PUBLIC_ASSISTANT_ID || "repurpora";

export function ThreadProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);

  const getThreads = useCallback(async (): Promise<Thread[]> => {
    if (!session) return [];
    const client = new Client({ apiUrl: API_URL, defaultHeaders: authHeaders(session) });
    const metadata = validate(ASSISTANT_ID) ? { assistant_id: ASSISTANT_ID } : { graph_id: ASSISTANT_ID };
    return client.threads.search({ metadata, limit: 100 });
  }, [session]);

  return (
    <ThreadContext.Provider value={{ getThreads, threads, setThreads, threadsLoading, setThreadsLoading }}>
      {children}
    </ThreadContext.Provider>
  );
}

export function useThreads() {
  const context = useContext(ThreadContext);
  if (context === undefined) throw new Error("useThreads must be used within a ThreadProvider");
  return context;
}
