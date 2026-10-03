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

test('login uses cookies and a CSRF header, then rotates the in-memory CSRF value', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({csrf_token: 'prelogin-csrf'})))
    .mockResolvedValueOnce(new Response(JSON.stringify({user: {id: 'a', username: 'Alice'}, csrf_token: 'signed-in-csrf'})))
    .mockResolvedValueOnce(new Response(null, {status: 204}));
  vi.stubGlobal('fetch', fetchMock);
  const {api} = await import('./client');
  await api.login('Alice', 'test-passphrase-123');
  const login = fetchMock.mock.calls[1][1];
  expect(login.credentials).toBe('include');
  expect(login.headers.get('X-CSRF-Token')).toBe('prelogin-csrf');
  await api.logout();
  expect(fetchMock.mock.calls[2][1].headers.get('X-CSRF-Token')).toBe('signed-in-csrf');
});

test('a private endpoint 401 emits a session-expired event', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({error: {message: 'Please sign in.'}}), {status: 401})));
  const expired = vi.fn();
  window.addEventListener('daybook:session-expired', expired);
  const {api} = await import('./client');
  await expect(api.dashboard()).rejects.toThrow('Please sign in.');
  expect(expired).toHaveBeenCalledOnce();
  window.removeEventListener('daybook:session-expired', expired);
});
