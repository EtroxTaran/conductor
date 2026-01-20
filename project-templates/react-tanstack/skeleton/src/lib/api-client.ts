import { queryOptions } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

// Example query options factory
// export const userQueryOptions = (userId: string) =>
//   queryOptions({
//     queryKey: ['users', userId],
//     queryFn: () => fetchJson<User>(`/users/${userId}`),
//     staleTime: 5 * 60 * 1000,
//   });

// export const usersQueryOptions = () =>
//   queryOptions({
//     queryKey: ['users'],
//     queryFn: () => fetchJson<User[]>('/users'),
//   });

export { fetchJson };
