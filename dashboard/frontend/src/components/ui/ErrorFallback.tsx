/**
 * Error fallback component for error boundaries
 */

import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./card";

interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
  title?: string;
  description?: string;
}

export function ErrorFallback({
  error,
  resetErrorBoundary,
  title = "Something went wrong",
  description = "An error occurred while rendering this component.",
}: ErrorFallbackProps) {
  return (
    <Card className="border-destructive/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <AlertTriangle
            className="h-5 w-5 text-destructive"
            aria-hidden="true"
          />
          <CardTitle className="text-destructive">{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground transition-colors">
            View error details
          </summary>
          <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-auto max-h-32">
            {error.message}
            {error.stack && (
              <>
                {"\n\n"}
                {error.stack}
              </>
            )}
          </pre>
        </details>
        <Button onClick={resetErrorBoundary} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" aria-hidden="true" />
          Try again
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * Minimal error fallback for inline use
 */
export function InlineErrorFallback({
  error,
  resetErrorBoundary,
}: Pick<ErrorFallbackProps, "error" | "resetErrorBoundary">) {
  return (
    <div className="flex items-center gap-3 p-4 rounded-md border border-destructive/50 bg-destructive/5">
      <AlertTriangle
        className="h-4 w-4 text-destructive flex-shrink-0"
        aria-hidden="true"
      />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-destructive">
          Error loading component
        </p>
        <p className="text-xs text-muted-foreground truncate">
          {error.message}
        </p>
      </div>
      <Button onClick={resetErrorBoundary} variant="ghost" size="sm">
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        <span className="sr-only">Retry</span>
      </Button>
    </div>
  );
}
