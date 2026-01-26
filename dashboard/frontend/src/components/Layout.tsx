/**
 * Main layout component
 */

import { useState } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import {
  Home,
  Settings,
  FolderKanban,
  BookOpen,
  Menu,
  X,
  Keyboard,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button, ShortcutsDialog } from "@/components/ui";
import { useKeyboardShortcuts } from "@/hooks";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Keyboard shortcuts
  const { shortcuts, isDialogOpen, setIsDialogOpen } = useKeyboardShortcuts();

  const navItems = [
    { path: "/", label: "Projects", icon: FolderKanban },
    { path: "/collection", label: "Collection", icon: BookOpen },
    { path: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-background font-sans antialiased">
      {/* Skip to main content link for accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:outline-none"
      >
        Skip to main content
      </a>

      {/* Glassmorphic Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link
              to="/"
              className="flex items-center space-x-2 transition-transform hover:scale-105"
            >
              <div className="rounded-lg bg-primary/10 p-1.5 ring-1 ring-primary/20">
                <Home className="h-5 w-5 text-primary" aria-hidden="true" />
              </div>
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                Conductor
              </span>
            </Link>

            {/* Desktop Navigation */}
            <nav
              className="hidden md:flex items-center space-x-1"
              aria-label="Main navigation"
            >
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      "group flex items-center space-x-2 rounded-md px-3 py-2 text-sm font-medium transition-all hover:bg-accent hover:text-accent-foreground",
                      isActive
                        ? "bg-secondary text-secondary-foreground shadow-sm ring-1 ring-border"
                        : "text-muted-foreground",
                    )}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 transition-colors",
                        isActive ? "text-primary" : "group-hover:text-primary",
                      )}
                      aria-hidden="true"
                    />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center space-x-2">
            {/* Keyboard shortcuts button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsDialogOpen(true)}
              aria-label="Show keyboard shortcuts (press ?)"
              className="hidden sm:flex"
            >
              <Keyboard className="h-5 w-5" aria-hidden="true" />
            </Button>

            {/* Mobile menu button */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-menu"
            >
              {isMobileMenuOpen ? (
                <X className="h-5 w-5" aria-hidden="true" />
              ) : (
                <Menu className="h-5 w-5" aria-hidden="true" />
              )}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <nav
            id="mobile-menu"
            className="md:hidden border-t border-border/40 bg-background/95 backdrop-blur-xl"
            aria-label="Mobile navigation"
          >
            <div className="container py-4 space-y-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      "flex items-center space-x-3 rounded-md px-4 py-3 text-sm font-medium transition-all",
                      isActive
                        ? "bg-secondary text-secondary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    )}
                    onClick={() => setIsMobileMenuOpen(false)}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon className="h-5 w-5" aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </nav>
        )}
      </header>

      {/* Main content */}
      <main
        id="main-content"
        className="container py-8 animate-fade-in-up"
        tabIndex={-1}
      >
        {children}
      </main>

      {/* Screen reader announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="announcements"
      />

      {/* Keyboard shortcuts dialog */}
      <ShortcutsDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        shortcuts={shortcuts}
      />
    </div>
  );
}
