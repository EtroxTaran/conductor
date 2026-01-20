import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';

const app = new Hono();

app.use('*', cors());
app.use('*', logger());

// Health check
app.get('/health', (c) => c.json({ status: 'ok' }));

// API routes
app.get('/api/v1/hello', (c) => {
  return c.json({ message: 'Hello from {{PROJECT_NAME}} API!' });
});

const port = Number(process.env['PORT']) || 3000;
console.log(`API starting on port ${port}`);

serve({
  fetch: app.fetch,
  port,
});

export default app;
