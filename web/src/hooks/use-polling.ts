"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling<T>(
  loader: (signal?: AbortSignal) => Promise<T>,
  intervalMs: number | null,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const controller = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    controller.current?.abort();
    const nextController = new AbortController();
    controller.current = nextController;
    setRefreshing(true);
    try {
      const nextData = await loader(nextController.signal);
      setData(nextData);
      setError(null);
    } catch (nextError) {
      if (nextError instanceof DOMException && nextError.name === "AbortError") {
        return;
      }
      setError(
        nextError instanceof Error
          ? nextError.message
          : "QUORUM could not load this view.",
      );
    } finally {
      if (!nextController.signal.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [loader]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void refresh(), 0);
    if (!intervalMs) {
      return () => {
        window.clearTimeout(initialLoad);
        controller.current?.abort();
      };
    }
    const tick = () => {
      if (document.visibilityState === "visible") {
        void refresh();
      }
    };
    const timer = window.setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
      controller.current?.abort();
    };
  }, [intervalMs, refresh]);

  return { data, error, loading, refreshing, refresh };
}
