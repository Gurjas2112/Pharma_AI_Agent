"use client";

import React, { createContext, useContext, ReactNode, useEffect } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import { uiMessageReducer, type UIMessage, type RemoveUIMessage } from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { toast } from "sonner";
import { useThreads } from "./Thread";
import { authHeaders, useAuth } from "./Auth";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2026";
export const ASSISTANT_ID = process.env.NEXT_PUBLIC_ASSISTANT_ID || "repurpora";

const sleep = (ms = 3000) => new Promise((r) => setTimeout(r, ms));

function StreamSession({ children, headers }: { children: ReactNode; headers: Record<string, string> }) {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads } = useThreads();
  const stream = useTypedStream({
    apiUrl: API_URL,
    assistantId: ASSISTANT_ID,
    threadId: threadId ?? null,
    defaultHeaders: headers,
    onCustomEvent: (event, options) => {
      options.mutate((prev) => ({ ...prev, ui: uiMessageReducer(prev.ui ?? [], event) }));
    },
    onThreadId: (id) => {
      setThreadId(id);
      sleep().then(() => getThreads().then(setThreads).catch(console.error));
    },
    onError: (err) => {
      toast.error("Agent run failed", { description: String((err as Error)?.message ?? err), richColors: true });
    },
  });

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
      })
      .catch(() =>
        toast.error("Agent server unreachable", {
          description: `Could not reach ${API_URL}. It may be waking up — retry in a few seconds.`,
          duration: 10000,
          richColors: true,
          closeButton: true,
        }),
      );
  }, []);

  return <StreamContext.Provider value={stream}>{children}</StreamContext.Provider>;
}

export const StreamProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { session, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Securing your session…
      </div>
    );
  }
  // key forces a fresh stream client when the access token rotates
  return (
    <StreamSession key={session?.access_token?.slice(-12) ?? "anon"} headers={authHeaders(session)}>
      {children}
    </StreamSession>
  );
};

export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) throw new Error("useStreamContext must be used within a StreamProvider");
  return context;
};

export default StreamContext;
