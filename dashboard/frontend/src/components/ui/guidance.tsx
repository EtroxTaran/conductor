import { HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./tooltip";
import { cn } from "@/lib/utils";

interface GuidanceProps {
  content: React.ReactNode;
  className?: string;
  /** Accessible label for the help button (default: "Help") */
  label?: string;
}

export function Guidance({
  content,
  className,
  label = "Help",
}: GuidanceProps) {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn(
              "inline-flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm",
              className,
            )}
            aria-label={label}
          >
            <HelpCircle
              className="h-4 w-4 text-muted-foreground hover:text-foreground cursor-help transition-colors"
              aria-hidden="true"
            />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{content}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
