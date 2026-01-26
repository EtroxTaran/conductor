/**
 * TanStack Query hooks for git operations
 */

import { useQuery } from "@tanstack/react-query";
import { gitApi } from "@/lib/api";

// Query keys
export const gitKeys = {
  all: ["git"] as const,
  info: (projectName: string) => [...gitKeys.all, "info", projectName] as const,
  log: (projectName: string) => [...gitKeys.all, "log", projectName] as const,
  diff: (projectName: string) => [...gitKeys.all, "diff", projectName] as const,
};

/**
 * Hook to fetch git repository info
 */
export function useGitInfo(projectName: string) {
  return useQuery({
    queryKey: gitKeys.info(projectName),
    queryFn: () => gitApi.getInfo(projectName),
    enabled: !!projectName,
    refetchInterval: 30000, // Poll every 30 seconds
    retry: false, // Don't retry if not a git repo
  });
}

/**
 * Hook to fetch git commit log
 */
export function useGitLog(projectName: string, limit = 20, skip = 0) {
  return useQuery({
    queryKey: [...gitKeys.log(projectName), { limit, skip }],
    queryFn: () => gitApi.getLog(projectName, limit, skip),
    enabled: !!projectName,
    staleTime: 60000, // 1 minute stale time
    retry: false,
  });
}

/**
 * Hook to fetch git diff
 */
export function useGitDiff(projectName: string, staged = false) {
  return useQuery({
    queryKey: [...gitKeys.diff(projectName), { staged }],
    queryFn: () => gitApi.getDiff(projectName, staged),
    enabled: !!projectName,
    refetchInterval: 10000, // Poll every 10 seconds for changes
    retry: false,
  });
}
