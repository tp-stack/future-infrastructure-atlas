import { useCallback, useEffect, useRef } from "react";

export function useDebounce<T extends (...args: never[]) => void>(
  fn: T,
  delay: number,
): { call: T; cancel: () => void } {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const cancel = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => cancel, [cancel]);

  const call = useCallback(
    (...args: Parameters<T>) => {
      cancel();
      timerRef.current = setTimeout(() => fnRef.current(...args), delay);
    },
    [cancel, delay],
  ) as unknown as T;

  return { call: call as unknown as T, cancel };
}
