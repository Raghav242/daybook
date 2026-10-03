import { afterEach, test, expect, vi } from 'vitest';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetModules(); });

test('browser requests use a configured API base without a duplicate trailing slash', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/api/');
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {status:200}));
  vi.stubGlobal('fetch', fetchMock);
  vi.resetModules();
  const { api } = await import('./client');
  await api.settings();
  expect(fetchMock).toHaveBeenCalledWith('https://api.example.test/api/settings', expect.any(Object));
});

test('local requests use the same-origin API path by default', async () => {
  vi.stubEnv('VITE_API_BASE_URL', '');
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {status:200}));
  vi.stubGlobal('fetch', fetchMock);
  vi.resetModules();
  const { api } = await import('./client');
  await api.settings();
  expect(fetchMock).toHaveBeenCalledWith('/api/settings', expect.any(Object));
});
