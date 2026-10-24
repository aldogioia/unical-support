import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Api } from '../api/api';
import { loginApiAuthLoginPost } from '../api/fn/auth/login-api-auth-login-post';
import { meApiAuthMeGet } from '../api/fn/auth/me-api-auth-me-get';
import { refreshAccessTokenApiAuthRefreshPost } from '../api/fn/auth/refresh-access-token-api-auth-refresh-post';
import { logoutApiAuthLogoutPost } from '../api/functions';
import { AuthService } from './auth.service';

describe('AuthService session regression', () => {
  let service: AuthService;
  let api: jasmine.SpyObj<Api>;
  let router: jasmine.SpyObj<Router>;
  let storage: Map<string, string>;
  const user = { id: 'operator-1', email: 'operatore@example.org', is_active: true, role: 'admin' as const };

  beforeEach(() => {
    storage = new Map();
    spyOn(Storage.prototype, 'getItem').and.callFake(key => storage.get(key) ?? null);
    spyOn(Storage.prototype, 'setItem').and.callFake((key, value) => { storage.set(key, value); });
    spyOn(Storage.prototype, 'removeItem').and.callFake(key => { storage.delete(key); });
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    TestBed.configureTestingModule({ providers: [
      provideHttpClient(), { provide: Api, useValue: api }, { provide: Router, useValue: router },
    ] });
    service = TestBed.inject(AuthService);
  });

  it('stores the token pair before loading the authenticated user', async () => {
    api.invoke.and.callFake(((operation: unknown) => {
      if (operation === loginApiAuthLoginPost) return Promise.resolve({ access_token: 'access-1', refresh_token: 'refresh-1' });
      if (operation === meApiAuthMeGet) {
        expect(service.accessToken).toBe('access-1');
        return Promise.resolve(user);
      }
      return Promise.reject(new Error('Unexpected API operation'));
    }) as any);
    await service.login(user.email, 'test-only-password');
    expect(api.invoke).toHaveBeenCalledWith(loginApiAuthLoginPost, { body: { email: user.email, password: 'test-only-password' } });
    expect(service.refreshToken).toBe('refresh-1');
    expect(service.isAuthenticated).toBeTrue();
    expect(service.currentUser()).toEqual(user);
  });

  it('does not create a session when credentials are rejected', async () => {
    api.invoke.and.returnValue(Promise.reject({ status: 401 }));
    await expectAsync(service.login(user.email, 'invalid-password')).toBeRejected();
    expect(service.accessToken).toBeNull();
    expect(service.refreshToken).toBeNull();
    expect(service.isAuthenticated).toBeFalse();
  });

  it('rotates both tokens when refreshing a session', async () => {
    storage.set('access_token', 'expired');
    storage.set('refresh_token', 'refresh-1');
    api.invoke.and.returnValue(Promise.resolve({ access_token: 'access-2', refresh_token: 'refresh-2' }) as any);
    expect(await service.tryRefreshToken()).toBe('access-2');
    expect(api.invoke).toHaveBeenCalledWith(refreshAccessTokenApiAuthRefreshPost, { refresh_token: 'refresh-1' });
    expect(service.accessToken).toBe('access-2');
    expect(service.refreshToken).toBe('refresh-2');
  });

  it('clears an expired session when refresh fails', async () => {
    storage.set('access_token', 'expired');
    storage.set('refresh_token', 'revoked');
    service.currentUser.set(user);
    api.invoke.and.returnValue(Promise.reject({ status: 401 }));
    expect(await service.tryRefreshToken()).toBeNull();
    expect(service.accessToken).toBeNull();
    expect(service.refreshToken).toBeNull();
    expect(service.currentUser()).toBeNull();
    expect(service.isAuthenticated).toBeFalse();
  });

  it('clears tokens and returns to login even when server logout fails', async () => {
    spyOn(console, 'error');
    storage.set('access_token', 'access-1');
    storage.set('refresh_token', 'refresh-1');
    service.currentUser.set(user);
    api.invoke.and.returnValue(Promise.reject({ status: 503 }));
    await service.logout();
    expect(api.invoke).toHaveBeenCalledWith(logoutApiAuthLogoutPost, { 'X-Refresh-Token': 'refresh-1' });
    expect(service.accessToken).toBeNull();
    expect(service.refreshToken).toBeNull();
    expect(service.currentUser()).toBeNull();
    expect(router.navigate).toHaveBeenCalledOnceWith(['/login']);
  });
});
