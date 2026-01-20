import { beforeAll, afterAll, afterEach } from 'vitest';
import { prisma } from '@/db/client.js';

beforeAll(async () => {
  // Connect to test database
  await prisma.$connect();
});

afterEach(async () => {
  // Clean up test data after each test
  // Add table cleanup as needed
  // await prisma.user.deleteMany();
});

afterAll(async () => {
  await prisma.$disconnect();
});
