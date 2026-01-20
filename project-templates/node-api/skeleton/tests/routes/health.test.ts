import { describe, it, expect } from 'vitest';
import app from '@/index.js';

describe('Health endpoint', () => {
  it('GET /health returns ok status', async () => {
    const res = await app.request('/health');
    expect(res.status).toBe(200);

    const json = await res.json();
    expect(json.status).toBe('ok');
    expect(json.services.database).toBe('ok');
  });
});
