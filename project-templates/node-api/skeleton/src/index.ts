import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger as honoLogger } from 'hono/logger';
import { env } from '@/lib/env.js';
import { logger } from '@/lib/logger.js';
import { errorHandler } from '@/middleware/error-handler.js';
import health from '@/routes/health.js';
import v1 from '@/routes/v1/index.js';

const app = new Hono();

// Global middleware
app.use('*', cors());
app.use('*', honoLogger());

// Error handler
app.onError(errorHandler);

// Routes
app.route('/health', health);
app.route('/api/v1', v1);

// 404 handler
app.notFound((c) => {
  return c.json({ error: 'Not Found' }, 404);
});

// Start server
const port = env.PORT;
logger.info(`Server starting on port ${port}`);

serve({
  fetch: app.fetch,
  port,
});

export default app;
