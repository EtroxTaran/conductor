/**
 * Tests for useWebSocket hook
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWebSocket } from "../useWebSocket";

// Mock createWebSocket
vi.mock("@/lib/api", () => ({
  createWebSocket: vi.fn(() => ({
    onopen: null,
    onclose: null,
    onmessage: null,
    onerror: null,
    send: vi.fn(),
    close: vi.fn(),
    readyState: 1, // OPEN
  })),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useWebSocket", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should not connect when projectName is undefined", () => {
    const { result } = renderHook(() => useWebSocket(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.isConnected).toBe(false);
    expect(result.current.lastEvent).toBe(null);
  });

  it("should connect when projectName is provided", async () => {
    const { createWebSocket } = await import("@/lib/api");
    const mockWs = {
      onopen: null as ((event: Event) => void) | null,
      onclose: null as ((event: CloseEvent) => void) | null,
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };
    vi.mocked(createWebSocket).mockReturnValue(mockWs as unknown as WebSocket);

    const { result } = renderHook(() => useWebSocket("test-project"), {
      wrapper: createWrapper(),
    });

    // Simulate connection
    act(() => {
      mockWs.onopen?.(new Event("open"));
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });

  it("should handle WebSocket messages and update lastEvent", async () => {
    const { createWebSocket } = await import("@/lib/api");
    const mockWs = {
      onopen: null as ((event: Event) => void) | null,
      onclose: null as ((event: CloseEvent) => void) | null,
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };
    vi.mocked(createWebSocket).mockReturnValue(mockWs as unknown as WebSocket);

    const onEvent = vi.fn();
    const { result } = renderHook(
      () => useWebSocket("test-project", { onEvent }),
      { wrapper: createWrapper() },
    );

    // Simulate connection
    act(() => {
      mockWs.onopen?.(new Event("open"));
    });

    // Simulate message
    const eventData = { type: "state_change", data: { phase: 2 } };
    act(() => {
      mockWs.onmessage?.(
        new MessageEvent("message", { data: JSON.stringify(eventData) }),
      );
    });

    await waitFor(() => {
      expect(result.current.lastEvent).toEqual(eventData);
      expect(onEvent).toHaveBeenCalledWith(eventData);
    });
  });

  it("should attempt reconnection on close", async () => {
    vi.useFakeTimers();
    const { createWebSocket } = await import("@/lib/api");
    const mockWs = {
      onopen: null as ((event: Event) => void) | null,
      onclose: null as ((event: CloseEvent) => void) | null,
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };
    vi.mocked(createWebSocket).mockReturnValue(mockWs as unknown as WebSocket);

    renderHook(
      () =>
        useWebSocket("test-project", {
          reconnectInterval: 1000,
          maxReconnectAttempts: 3,
        }),
      { wrapper: createWrapper() },
    );

    // Simulate connection then close
    act(() => {
      mockWs.onopen?.(new Event("open"));
    });

    act(() => {
      mockWs.onclose?.(new CloseEvent("close"));
    });

    // Fast-forward to trigger reconnect
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    // Should have been called twice (initial + reconnect attempt)
    expect(createWebSocket).toHaveBeenCalledTimes(2);

    vi.useRealTimers();
  });

  it("should call onError when WebSocket errors", async () => {
    const { createWebSocket } = await import("@/lib/api");
    const mockWs = {
      onopen: null as ((event: Event) => void) | null,
      onclose: null as ((event: CloseEvent) => void) | null,
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };
    vi.mocked(createWebSocket).mockReturnValue(mockWs as unknown as WebSocket);

    const onError = vi.fn();
    renderHook(() => useWebSocket("test-project", { onError }), {
      wrapper: createWrapper(),
    });

    // Simulate error
    const errorEvent = new Event("error");
    act(() => {
      mockWs.onerror?.(errorEvent);
    });

    expect(onError).toHaveBeenCalledWith(errorEvent);
  });

  it("should send data through WebSocket", async () => {
    const { createWebSocket } = await import("@/lib/api");
    const mockWs = {
      onopen: null as ((event: Event) => void) | null,
      onclose: null as ((event: CloseEvent) => void) | null,
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };
    vi.mocked(createWebSocket).mockReturnValue(mockWs as unknown as WebSocket);

    const { result } = renderHook(() => useWebSocket("test-project"), {
      wrapper: createWrapper(),
    });

    act(() => {
      mockWs.onopen?.(new Event("open"));
    });

    const testData = { action: "test" };
    act(() => {
      result.current.send(testData);
    });

    expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify(testData));
  });

  it("should disconnect and clean up on unmount", async () => {
    const { createWebSocket } = await import("@/lib/api");
    const mockWs = {
      onopen: null as ((event: Event) => void) | null,
      onclose: null as ((event: CloseEvent) => void) | null,
      onmessage: null as ((event: MessageEvent) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };
    vi.mocked(createWebSocket).mockReturnValue(mockWs as unknown as WebSocket);

    const { unmount } = renderHook(() => useWebSocket("test-project"), {
      wrapper: createWrapper(),
    });

    act(() => {
      mockWs.onopen?.(new Event("open"));
    });

    unmount();

    expect(mockWs.close).toHaveBeenCalled();
  });
});
