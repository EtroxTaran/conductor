/**
 * Keyboard shortcuts help dialog
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Shortcut, getShortcutsByCategory } from "@/hooks/useKeyboardShortcuts";
import { cn } from "@/lib/utils";

interface ShortcutsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  shortcuts: Shortcut[];
}

const categoryLabels: Record<string, string> = {
  navigation: "Navigation",
  actions: "Actions",
  other: "Other",
};

const categoryOrder = ["navigation", "actions", "other"];

function KeyBadge({ children }: { children: React.ReactNode }) {
  return (
    <kbd
      className={cn(
        "inline-flex items-center justify-center",
        "min-w-[1.5rem] h-6 px-1.5",
        "text-xs font-medium font-mono",
        "bg-muted border border-border rounded",
        "shadow-sm",
      )}
    >
      {children}
    </kbd>
  );
}

function ShortcutKey({ keyStr }: { keyStr: string }) {
  // Split multi-key shortcuts (e.g., "g p" -> ["g", "p"])
  const keys = keyStr.split(" ");

  return (
    <div className="flex items-center gap-1">
      {keys.map((key, index) => (
        <span key={index} className="flex items-center gap-1">
          <KeyBadge>{key === "?" ? "?" : key.toUpperCase()}</KeyBadge>
          {index < keys.length - 1 && (
            <span className="text-muted-foreground text-xs">then</span>
          )}
        </span>
      ))}
    </div>
  );
}

export function ShortcutsDialog({
  open,
  onOpenChange,
  shortcuts,
}: ShortcutsDialogProps) {
  const groupedShortcuts = getShortcutsByCategory(shortcuts);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
          <DialogDescription>
            Use these shortcuts to navigate quickly
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {categoryOrder.map((category) => {
            const categoryShortcuts = groupedShortcuts[category];
            if (!categoryShortcuts?.length) return null;

            return (
              <div key={category}>
                <h3 className="text-sm font-medium text-muted-foreground mb-3">
                  {categoryLabels[category] || category}
                </h3>
                <div className="space-y-2">
                  {categoryShortcuts.map((shortcut) => (
                    <div
                      key={shortcut.key}
                      className="flex items-center justify-between py-1.5"
                    >
                      <span className="text-sm">{shortcut.description}</span>
                      <ShortcutKey keyStr={shortcut.key} />
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="pt-4 border-t text-center">
          <p className="text-xs text-muted-foreground">
            Press <KeyBadge>?</KeyBadge> to show this dialog
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
