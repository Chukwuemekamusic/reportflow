import { set } from "date-fns";
import { useEffect, useRef, useState, useCallback } from "react";

export type WSEvent =
  | {
      event: "progress";
      job_id: string;
      progress: number;
      stage: string;
      eta_secs: number;
    }
  | { event: "completed"; job_id: string; progress: 100; download_url: string }
  | { event: "failed"; job_id: string; error_message: string }
  | { event: "queued" | "running"; job_id: string };

export type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface UseWebSocketOptions {
  onEvent?: (event: WSEvent) => void;
  onComplete?: (downloadUrl: string) => void;
  onFail?: (errorMessage: string) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<WSStatus>("idle");
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options; // keep options ref fresh without re-subscribing

  const connect = useCallback((jobId: string, token: string) => {
    // Close any existing connection before opening a new one
    if (wsRef.current) {
      wsRef.current.close();
    }

    // WebSocket connections cannot go through the Vite HTTP proxy.
    // We connect directly to the FastAPI server on port 8000.
    // In production, this would be wss://your-domain.com
    const wsBase =
      window.location.hostname === "localhost"
        ? "ws://localhost:8000"
        : `wss://${window.location.host}`;
    const url = `${wsBase}/api/v1/reports/${jobId}/stream?token=${encodeURIComponent(token)}`;

    setStatus("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setStatus("open");

    ws.onmessage = (messageEvent) => {
      try {
        const parsed: WSEvent = JSON.parse(messageEvent.data);
        setLastEvent(parsed);
        optionsRef.current.onEvent?.(parsed);

        if (parsed.event === "completed") {
          optionsRef.current.onComplete?.(parsed.download_url);
          ws.close(1000, "Job completed");
          setStatus("closed");
        } else if (parsed.event === "failed") {
          optionsRef.current.onFail?.(parsed.error_message);
          ws.close(1000, "Job failed");
          setStatus("error");
        }
      } catch (error) {
        // ignore unparseable frames
      }
    };

    ws.onerror = () => setStatus("error");
    ws.onclose = (e) => {
      if (e.code !== 1000) setStatus("error");
      else setStatus("closed");
    };
  }, []);

  // Clean up on component unmount — don't leave dangling connections
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return { status, lastEvent, connect };
}
