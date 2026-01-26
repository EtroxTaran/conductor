/**
 * TanStack Router route tree
 */

import { createRootRoute, createRoute, Outlet } from "@tanstack/react-router";
import { ErrorBoundary } from "react-error-boundary";
import { Layout } from "@/components/Layout";
import { ErrorFallback } from "@/components/ui";
import { ProjectsPage } from "./ProjectsPage";
import { ProjectDashboard } from "./ProjectDashboard";
import { SettingsPage } from "./SettingsPage";
import { CollectionPage } from "@/components/collection/CollectionPage";

// Root route with layout and error boundary
const rootRoute = createRootRoute({
  component: () => (
    <Layout>
      <ErrorBoundary
        FallbackComponent={ErrorFallback}
        onReset={() => {
          // Reset app state on error recovery
          window.location.reload();
        }}
      >
        <Outlet />
      </ErrorBoundary>
    </Layout>
  ),
});

// Index route (project list)
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ProjectsPage,
});

// Project dashboard route
const projectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/project/$name",
  component: ProjectDashboard,
});

// Collection route
const collectionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/collection",
  component: CollectionPage,
});

// Settings route
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsPage,
});

// Create the route tree
export const routeTree = rootRoute.addChildren([
  indexRoute,
  projectRoute,
  collectionRoute,
  settingsRoute,
]);
