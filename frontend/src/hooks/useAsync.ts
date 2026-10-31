import { useEffect, useState } from 'react';

export interface AsyncState<T> { data?: T; error?: Error; loading: boolean }

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [state, set] = useState<AsyncState<T>>({ loading: true });
  useEffect(() => {
    let live = true;
    set({ loading: true });
    fn().then(data => live && set({ data, loading: false })).catch(error => live && set({ error, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
