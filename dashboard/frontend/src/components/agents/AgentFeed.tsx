/**
 * Agent activity feed component
 */

import { useQuery } from '@tanstack/react-query';
import { agentsApi } from '@/lib/api';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ScrollArea,
  Separator,
} from '@/components/ui';
import { formatDate, formatDuration, formatCost, getAgentName } from '@/lib/utils';
import type { AgentStatus, AuditEntry } from '@/types';

interface AgentFeedProps {
  projectName: string;
}

function AgentCard({ agent }: { agent: AgentStatus }) {
  return (
    <Card>
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{getAgentName(agent.agent)}</CardTitle>
          <Badge variant={agent.available ? 'success' : 'destructive'}>
            {agent.available ? 'Available' : 'Unavailable'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Invocations</span>
            <p className="font-medium">{agent.total_invocations}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Success Rate</span>
            <p className="font-medium">{(agent.success_rate * 100).toFixed(1)}%</p>
          </div>
          <div>
            <span className="text-muted-foreground">Avg Duration</span>
            <p className="font-medium">{formatDuration(agent.avg_duration_seconds)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Total Cost</span>
            <p className="font-medium">{formatCost(agent.total_cost_usd)}</p>
          </div>
        </div>
        {agent.last_invocation && (
          <p className="mt-2 text-xs text-muted-foreground">
            Last: {formatDate(agent.last_invocation)}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function AuditEntryRow({ entry }: { entry: AuditEntry }) {
  return (
    <div className="flex items-center justify-between py-2 border-b">
      <div className="flex items-center space-x-3">
        <Badge variant="secondary" className="text-xs">
          {getAgentName(entry.agent)}
        </Badge>
        <span className="text-sm font-medium">{entry.task_id}</span>
        <Badge
          variant={entry.status === 'success' ? 'success' : entry.status === 'failed' ? 'destructive' : 'secondary'}
          className="text-xs"
        >
          {entry.status}
        </Badge>
      </div>
      <div className="flex items-center space-x-4 text-xs text-muted-foreground">
        {entry.duration_seconds !== undefined && (
          <span>{formatDuration(entry.duration_seconds)}</span>
        )}
        {entry.cost_usd !== undefined && <span>{formatCost(entry.cost_usd)}</span>}
        {entry.timestamp && <span>{formatDate(entry.timestamp)}</span>}
      </div>
    </div>
  );
}

export function AgentFeed({ projectName }: AgentFeedProps) {
  const { data: agentStatus } = useQuery({
    queryKey: ['agents', projectName],
    queryFn: () => agentsApi.getStatus(projectName),
  });

  const { data: auditData } = useQuery({
    queryKey: ['audit', projectName],
    queryFn: () => agentsApi.getAudit(projectName, { limit: 50 }),
    refetchInterval: 5000,
  });

  const agents = agentStatus?.agents || [];
  const entries = auditData?.entries || [];

  return (
    <div className="space-y-6">
      {/* Agent status cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {agents.map((agent) => (
          <AgentCard key={agent.agent} agent={agent} />
        ))}
      </div>

      <Separator />

      {/* Recent activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest agent invocations</CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[300px]">
            {entries.map((entry) => (
              <AuditEntryRow key={entry.id} entry={entry} />
            ))}
            {entries.length === 0 && (
              <p className="text-sm text-muted-foreground">No activity yet</p>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
