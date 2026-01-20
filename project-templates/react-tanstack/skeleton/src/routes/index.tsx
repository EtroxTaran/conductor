import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold tracking-tight">
        Welcome to {{PROJECT_NAME}}
      </h1>
      <p className="text-muted-foreground text-lg">
        A React 19 application built with TanStack Router, Query, Form, and Table.
      </p>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <FeatureCard
          title="TanStack Router"
          description="Type-safe file-based routing with preloading and caching."
        />
        <FeatureCard
          title="TanStack Query"
          description="Powerful data fetching and caching for server state."
        />
        <FeatureCard
          title="TanStack Form"
          description="Headless form management with validation support."
        />
        <FeatureCard
          title="Shadcn/ui"
          description="Beautiful, accessible components built with Radix UI."
        />
        <FeatureCard
          title="Tailwind CSS"
          description="Utility-first CSS framework for rapid styling."
        />
        <FeatureCard
          title="Vitest"
          description="Fast unit testing with React Testing Library."
        />
      </div>
    </div>
  );
}

function FeatureCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
