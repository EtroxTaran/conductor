import { Hono } from 'hono';
import { prisma } from '@/db/client.js';

const health = new Hono();

health.get('/', async (c) => {
  try {
    // Check database connection
    await prisma.$queryRaw`SELECT 1`;

    return c.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      services: {
        database: 'ok',
      },
    });
  } catch (error) {
    return c.json(
      {
        status: 'error',
        timestamp: new Date().toISOString(),
        services: {
          database: 'error',
        },
      },
      503
    );
  }
});

export default health;
