import { useEffect, useRef, useState } from "react";
export function useResource<T>(
  key: string,
  load: (signal: AbortSignal) => Promise<T>,
  enabled = true,
) {
  const loader = useRef(load);
  loader.current = load;
  const [state, setState] = useState<{
    resourceKey: string;
    data?: T;
    error?: string;
    loading: boolean;
  }>({ resourceKey: key, loading: enabled });
  useEffect(() => {
    const controller = new AbortController();
    if (!enabled) {
      setState({ resourceKey: key, loading: false });
      return () => controller.abort();
    }
    setState({ resourceKey: key, loading: true });
    loader
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ resourceKey: key, data, loading: false });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({
            resourceKey: key,
            error: error.message || "Unexpected response",
            loading: false,
          });
      });
    return () => controller.abort();
  }, [key, enabled]);
  return state.resourceKey === key
    ? state
    : { loading: enabled, data: undefined, error: undefined };
}
export function useDebounce<T>(value: T, delay = 350) {
  const [next, setNext] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setNext(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return next;
}
export function useAction() {
  const ref = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => ref.current?.abort(), []);
  async function execute<T>(
    work: (signal: AbortSignal) => Promise<T>,
    done: (value: T) => void,
  ) {
    if (ref.current) return;
    const controller = new AbortController();
    ref.current = controller;
    setBusy(true);
    setError("");
    try {
      const data = await work(controller.signal);
      if (!controller.signal.aborted) done(data);
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      ref.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return { busy, error, execute };
}
