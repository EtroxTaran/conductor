import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { userService } from '@/services/user.service.js';

const users = new Hono();

// Validation schemas
const createUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
});

const updateUserSchema = z.object({
  email: z.string().email().optional(),
  name: z.string().min(1).max(100).optional(),
});

const listQuerySchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

// GET /api/v1/users
users.get('/', zValidator('query', listQuerySchema), async (c) => {
  const { page, limit } = c.req.valid('query');
  const { users, total } = await userService.findMany({ page, limit });

  return c.json({
    users,
    pagination: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit),
    },
  });
});

// GET /api/v1/users/:id
users.get('/:id', async (c) => {
  const id = c.req.param('id');
  const user = await userService.findById(id);

  if (!user) {
    return c.json({ error: 'User not found' }, 404);
  }

  return c.json({ user });
});

// POST /api/v1/users
users.post('/', zValidator('json', createUserSchema), async (c) => {
  const data = c.req.valid('json');

  // Check if email already exists
  const existing = await userService.findByEmail(data.email);
  if (existing) {
    return c.json({ error: 'Email already in use' }, 409);
  }

  const user = await userService.create(data);
  return c.json({ user }, 201);
});

// PUT /api/v1/users/:id
users.put('/:id', zValidator('json', updateUserSchema), async (c) => {
  const id = c.req.param('id');
  const data = c.req.valid('json');

  const existing = await userService.findById(id);
  if (!existing) {
    return c.json({ error: 'User not found' }, 404);
  }

  // Check email uniqueness if changing
  if (data.email && data.email !== existing.email) {
    const emailExists = await userService.findByEmail(data.email);
    if (emailExists) {
      return c.json({ error: 'Email already in use' }, 409);
    }
  }

  const user = await userService.update(id, data);
  return c.json({ user });
});

// DELETE /api/v1/users/:id
users.delete('/:id', async (c) => {
  const id = c.req.param('id');

  const existing = await userService.findById(id);
  if (!existing) {
    return c.json({ error: 'User not found' }, 404);
  }

  await userService.delete(id);
  return c.json({ success: true });
});

export default users;
