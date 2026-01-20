import { HTTPException } from 'hono/http-exception';
import type { ErrorHandler } from 'hono';
import { logger } from '@/lib/logger.js';
import { env } from '@/lib/env.js';

export const errorHandler: ErrorHandler = (err, c) => {
  logger.error({ err }, 'Unhandled error');

  if (err instanceof HTTPException) {
    return c.json({ error: err.message }, err.status);
  }

  // Don't expose internal errors in production
  const message =
    env.NODE_ENV === 'production'
      ? 'Internal Server Error'
      : err.message || 'Internal Server Error';

  return c.json({ error: message }, 500);
};
