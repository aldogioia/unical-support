import { Injectable, signal, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Api } from '../api/api';
import { logoutApiAuthLogoutPost } from '../api/functions';
import { loginApiAuthLoginPost } from '../api/fn/auth/login-api-auth-login-post';
import { meApiAuthMeGet } from '../api/fn/auth/me-api-auth-me-get';
import { refreshAccessTokenApiAuthRefreshPost } from '../api/fn/auth/refresh-access-token-api-auth-refresh-post';
import { UserResponse } from '../api/models/user-response';
import { HttpClient } from '@angular/common/http';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private api = inject(Api);
  private router = inject(Router);
  private http = inject(HttpClient);

  currentUser = signal<UserResponse | null>(null);

  get accessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  get refreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  get isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  private setTokens(accessToken: string, refreshToken: string) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }

  private clearTokens() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }

  async login(email: string, password: string): Promise<void> {
    const tokens = await this.api.invoke(loginApiAuthLoginPost, {
      body: { email, password },
    });
    this.setTokens(tokens.access_token, tokens.refresh_token);
    await this.loadCurrentUser();
  }

  async loadCurrentUser(): Promise<UserResponse | null> {
    if (!this.accessToken) {
      this.currentUser.set(null);
      return null;
    }
    try {
      const user = await this.api.invoke(meApiAuthMeGet, {});
      this.currentUser.set(user);
      return user;
    } catch {
      this.currentUser.set(null);
      return null;
    }
  }

  /**
   * Usato dall'interceptor per rinnovare l'access token quando scade
   * (dura solo 15 minuti). Ritorna il nuovo access token, o null se anche
   * il refresh token non è più valido (in quel caso bisogna rifare login).
   */
  async tryRefreshToken(): Promise<string | null> {
    const rt = this.refreshToken;
    if (!rt) return null;
    try {
      const tokens = await this.api.invoke(refreshAccessTokenApiAuthRefreshPost, {
        refresh_token: rt
      });

      this.setTokens(tokens.access_token, tokens.refresh_token);
      return tokens.access_token;
    } catch {
      this.clearTokens();
      this.currentUser.set(null);
      return null;
    }
  }

  async logout(): Promise<void> {
    const rt = this.refreshToken;

    try {
      if (rt) {
        await this.api.invoke(logoutApiAuthLogoutPost, {
          'X-Refresh-Token': rt
        });
      }
    } catch (error) {
      console.error('Errore durante la revoca dei token sul server:', error);
    } finally {
      this.clearTokens();
      this.currentUser.set(null);
      this.router.navigate(['/login']);
    }
  }
}