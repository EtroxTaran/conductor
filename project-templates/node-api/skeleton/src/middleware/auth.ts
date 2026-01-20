import { HTTPException } from 'hono/http-exception';
import type { MiddlewareHandler } from 'hono';

// Placeholder auth middleware - implement based on your auth strategy
export const authMiddleware: MiddlewareHandler = async (c, next) => {
  const authHeader = c.req.header('Authorization');

  if (!authHeader?.startsWith('Bearer ')) {
    throw new HTTPException(401, { message: 'Missing or invalid token' });
  }

  const token = authHeader.slice(7);

  // TODO: Implement token verification
  // const payload = await verifyToken(token);
  // if (!payload) {
  //   throw new HTTPException(401, { message: 'Invalid token' });
  // }
  // c.set('user', payload);

  if (!token) {
    throw new HTTPException(401, { message: 'Invalid token' });
  }

  await next();
};
