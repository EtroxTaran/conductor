import { prisma } from '@/db/client.js';
import type { User, Prisma } from '@prisma/client';

interface FindManyOptions {
  page: number;
  limit: number;
}

interface FindManyResult {
  users: User[];
  total: number;
}

export const userService = {
  findMany: async ({ page, limit }: FindManyOptions): Promise<FindManyResult> => {
    const skip = (page - 1) * limit;

    const [users, total] = await Promise.all([
      prisma.user.findMany({
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' },
      }),
      prisma.user.count(),
    ]);

    return { users, total };
  },

  findById: (id: string): Promise<User | null> => {
    return prisma.user.findUnique({ where: { id } });
  },

  findByEmail: (email: string): Promise<User | null> => {
    return prisma.user.findUnique({ where: { email } });
  },

  create: (data: Prisma.UserCreateInput): Promise<User> => {
    return prisma.user.create({ data });
  },

  update: (id: string, data: Prisma.UserUpdateInput): Promise<User> => {
    return prisma.user.update({ where: { id }, data });
  },

  delete: (id: string): Promise<User> => {
    return prisma.user.delete({ where: { id } });
  },
};
