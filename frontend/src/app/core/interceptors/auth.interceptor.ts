import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

const PUBLIC_PATHS = ['/api/auth/login', '/api/auth/refresh'];

function isPublicRequest(url: string): boolean {
  return PUBLIC_PATHS.some(p => url.includes(p));
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.accessToken;

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((error: unknown) => {
      // Se scade l'access token (401) su una richiesta autenticata (non login/refresh),
      // proviamo a rinnovarlo una volta sola e a ripetere la richiesta originale.
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !isPublicRequest(req.url) &&
        authService.refreshToken
      ) {
        return from(authService.tryRefreshToken()).pipe(
          switchMap((newToken) => {
            if (!newToken) {
              authService.logout();
              return throwError(() => error);
            }
            const retryReq = req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } });
            return next(retryReq);
          })
        );
      }

      if (error instanceof HttpErrorResponse && error.status === 401 && !isPublicRequest(req.url)) {
        authService.logout();
      }

      return throwError(() => error);
    })
  );
};
