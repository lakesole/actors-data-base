import { useCallback, useEffect, useRef, useState } from "react";

type AsyncState<T> = {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
};

/**
 * 비동기 조회를 실행하고 결과/에러/로딩 상태를 돌려준다. deps가 바뀌면 다시 조회한다.
 * 늦게 도착한 이전 요청의 결과는 무시한다.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ data: undefined, error: undefined, loading: true });
  const requestId = useRef(0);

  const run = useCallback(fn, deps);

  const reload = useCallback(async () => {
    const id = ++requestId.current;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    try {
      const data = await run();
      if (id === requestId.current) setState({ data, error: undefined, loading: false });
    } catch (e) {
      if (id === requestId.current) {
        setState({ data: undefined, error: e instanceof Error ? e.message : String(e), loading: false });
      }
    }
  }, [run]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { ...state, reload };
}
