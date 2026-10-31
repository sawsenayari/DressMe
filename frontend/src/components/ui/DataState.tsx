import type { ReactNode } from 'react';
import type { AsyncState } from '../../hooks/useAsync';
import { EmptyState } from './EmptyState';

interface Props<T> {
  state: AsyncState<T>;
  pending: string;      // message shown while the model/endpoint isn't available
  endpoint?: string;    // shown to help the integrator
  isEmpty?: (d: T) => boolean;
  children: (data: T) => ReactNode;
}

export function DataState<T>({ state, pending, endpoint, isEmpty, children }: Props<T>) {
  if (state.loading) return <div className="skeleton" aria-busy="true" />;
  if (state.error || state.data === undefined || isEmpty?.(state.data)) return <EmptyState text={pending} endpoint={endpoint} />;
  return <>{children(state.data)}</>;
}
