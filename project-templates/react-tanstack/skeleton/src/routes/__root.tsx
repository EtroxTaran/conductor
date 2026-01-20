import { createRootRouteWithContext, Outlet } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/router-devtools';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import type { QueryClient } from '@tanstack/react-query';

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});

function RootLayout() {
  return (
    <>
      <div className="min-h-screen flex flex-col">
        <header className="border-b">
          <div className="container mx-auto px-4 py-4">
            <nav className="flex items-center gap-6">
              <a href="/" className="text-lg font-semibold">
                {{PROJECT_NAME}}
              </a>
            </nav>
          </div>
        </header>
        <main className="flex-1 container mx-auto px-4 py-8">
          <Outlet />
        </main>
        <footer className="border-t py-4">
          <div className="container mx-auto px-4 text-center text-muted-foreground text-sm">
            Built with React + TanStack
          </div>
        </footer>
      </div>
      {import.meta.env.DEV && (
        <>
          <TanStackRouterDevtools position="bottom-right" />
          <ReactQueryDevtools position="bottom" />
        </>
      )}
    </>
  );
}
