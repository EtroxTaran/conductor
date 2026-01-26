/**
 * Git integration panel for project dashboard
 */

import { useState } from "react";
import {
  GitBranch,
  GitCommit,
  AlertCircle,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  FileEdit,
  Loader2,
} from "lucide-react";
import { useGitInfo, useGitLog, useGitDiff } from "@/hooks";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ScrollArea,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Separator,
} from "@/components/ui";
import { cn } from "@/lib/utils";

interface GitPanelProps {
  projectName: string;
}

function CommitList({ projectName }: { projectName: string }) {
  const [page, setPage] = useState(0);
  const limit = 20;
  const { data, isLoading, error } = useGitLog(
    projectName,
    limit,
    page * limit,
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32" role="status">
        <Loader2
          className="h-6 w-6 animate-spin text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground">
        Unable to load commit history
      </div>
    );
  }

  const commits = data?.commits || [];
  const total = data?.total || 0;
  const hasMore = (page + 1) * limit < total;
  const hasPrev = page > 0;

  return (
    <div className="space-y-4">
      <ScrollArea className="h-[350px]">
        <div className="space-y-2 pr-4">
          {commits.map((commit) => (
            <div
              key={commit.hash}
              className="flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
            >
              <div className="flex-shrink-0 mt-1">
                <GitCommit
                  className="h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <p className="text-sm font-medium leading-tight line-clamp-2">
                  {commit.message}
                </p>
                <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                  <code className="px-1.5 py-0.5 rounded bg-muted font-mono">
                    {commit.short_hash}
                  </code>
                  <span>{commit.author}</span>
                  <span className="hidden sm:inline">
                    {new Date(commit.date).toLocaleDateString()}
                  </span>
                  {commit.files_changed > 0 && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      {commit.files_changed} files
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          ))}
          {commits.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No commits found
            </p>
          )}
        </div>
      </ScrollArea>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Showing {page * limit + 1}-{Math.min((page + 1) * limit, total)} of{" "}
          {total}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p - 1)}
            disabled={!hasPrev}
            aria-label="Previous page"
          >
            <ChevronUp className="h-4 w-4 mr-1" aria-hidden="true" />
            Newer
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasMore}
            aria-label="Next page"
          >
            Older
            <ChevronDown className="h-4 w-4 ml-1" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function DirtyFilesList({ files }: { files: string[] }) {
  if (files.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-4">
        No uncommitted changes
      </div>
    );
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-1 pr-4">
        {files.map((file) => (
          <div
            key={file}
            className="flex items-center gap-2 text-sm py-1.5 px-2 rounded hover:bg-muted/50"
          >
            <FileEdit
              className="h-3.5 w-3.5 text-yellow-500 flex-shrink-0"
              aria-hidden="true"
            />
            <span className="font-mono text-xs truncate">{file}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}

function DiffView({ projectName }: { projectName: string }) {
  const [staged, setStaged] = useState(false);
  const { data, isLoading, error } = useGitDiff(projectName, staged);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32" role="status">
        <Loader2
          className="h-6 w-6 animate-spin text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground">
        Unable to load diff
      </div>
    );
  }

  const diff = data?.diff || "";
  const files = data?.files || [];
  const insertions = data?.insertions || 0;
  const deletions = data?.deletions || 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            variant={staged ? "outline" : "secondary"}
            size="sm"
            onClick={() => setStaged(false)}
          >
            Unstaged
          </Button>
          <Button
            variant={staged ? "secondary" : "outline"}
            size="sm"
            onClick={() => setStaged(true)}
          >
            Staged
          </Button>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-green-600">+{insertions}</span>
          <span className="text-red-600">-{deletions}</span>
          <span className="text-muted-foreground">{files.length} files</span>
        </div>
      </div>

      {diff ? (
        <ScrollArea className="h-[300px] border rounded-md bg-muted/30">
          <pre className="text-xs font-mono p-4 whitespace-pre-wrap break-all">
            {diff.split("\n").map((line, i) => (
              <span
                key={i}
                className={cn(
                  "block",
                  line.startsWith("+") && !line.startsWith("+++")
                    ? "text-green-600 bg-green-500/10"
                    : line.startsWith("-") && !line.startsWith("---")
                      ? "text-red-600 bg-red-500/10"
                      : line.startsWith("@@")
                        ? "text-blue-600"
                        : "",
                )}
              >
                {line}
              </span>
            ))}
          </pre>
        </ScrollArea>
      ) : (
        <div className="flex items-center justify-center h-[300px] text-muted-foreground">
          No {staged ? "staged" : "unstaged"} changes
        </div>
      )}
    </div>
  );
}

export function GitPanel({ projectName }: GitPanelProps) {
  const { data: gitInfo, isLoading, error } = useGitInfo(projectName);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48" role="status">
        <Loader2
          className="h-6 w-6 animate-spin text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-4">
        <AlertCircle
          className="h-8 w-8 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-muted-foreground">
          Not a git repository or git is not available
        </p>
      </div>
    );
  }

  if (!gitInfo) {
    return null;
  }

  // Parse GitHub/GitLab URL for linking
  const repoUrl = gitInfo.repo_url;
  const webUrl = repoUrl
    ? repoUrl
        .replace(/\.git$/, "")
        .replace(/^git@github\.com:/, "https://github.com/")
        .replace(/^git@gitlab\.com:/, "https://gitlab.com/")
    : null;

  return (
    <div className="space-y-6">
      {/* Git Status Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch
                className="h-5 w-5 text-muted-foreground"
                aria-hidden="true"
              />
              <CardTitle className="text-lg">Repository Status</CardTitle>
            </div>
            {webUrl && (
              <a
                href={webUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
              >
                View on GitHub
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              </a>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Branch */}
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Branch</p>
              <div className="flex items-center gap-2">
                <code className="text-sm font-semibold">{gitInfo.branch}</code>
                {gitInfo.ahead > 0 && (
                  <Badge variant="secondary" className="text-[10px]">
                    {gitInfo.ahead} ahead
                  </Badge>
                )}
                {gitInfo.behind > 0 && (
                  <Badge variant="destructive" className="text-[10px]">
                    {gitInfo.behind} behind
                  </Badge>
                )}
              </div>
            </div>

            {/* Commit */}
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Last Commit</p>
              <code className="text-sm font-mono">{gitInfo.commit}</code>
            </div>

            {/* Status */}
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Status</p>
              <Badge variant={gitInfo.is_dirty ? "warning" : "success"}>
                {gitInfo.is_dirty ? "Uncommitted Changes" : "Clean"}
              </Badge>
            </div>

            {/* Dirty Files Count */}
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Changed Files</p>
              <p className="text-sm font-semibold">
                {gitInfo.dirty_files.length}
              </p>
            </div>
          </div>

          {gitInfo.last_commit_msg && (
            <>
              <Separator className="my-4" />
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">
                  Last Commit Message
                </p>
                <p className="text-sm line-clamp-2">
                  {gitInfo.last_commit_msg}
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Tabs for History, Changes, Diff */}
      <Tabs defaultValue="history" className="space-y-4">
        <TabsList>
          <TabsTrigger value="history">Commit History</TabsTrigger>
          <TabsTrigger value="changes">
            Uncommitted
            {gitInfo.dirty_files.length > 0 && (
              <Badge variant="secondary" className="ml-2 text-[10px]">
                {gitInfo.dirty_files.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="diff">Diff</TabsTrigger>
        </TabsList>

        <TabsContent value="history" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Recent Commits</CardTitle>
              <CardDescription>Browse the commit history</CardDescription>
            </CardHeader>
            <CardContent>
              <CommitList projectName={projectName} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="changes" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Uncommitted Files</CardTitle>
              <CardDescription>Files with local changes</CardDescription>
            </CardHeader>
            <CardContent>
              <DirtyFilesList files={gitInfo.dirty_files} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="diff" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Changes Diff</CardTitle>
              <CardDescription>View line-by-line changes</CardDescription>
            </CardHeader>
            <CardContent>
              <DiffView projectName={projectName} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
