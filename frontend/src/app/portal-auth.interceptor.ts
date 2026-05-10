import {
  HttpClient,
  HttpContext,
  HttpContextToken,
  HttpErrorResponse,
  HttpInterceptorFn,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { environment } from '../environments/environment';
import { PortalTokenStore } from './portal-token.store';
import type { PortalAuthResponse } from './services/client-portal.service';

/** Запросы с этим флагом не получают Bearer и не запускают цикл refresh. */
export const PORTAL_SKIP_AUTH = new HttpContextToken<boolean>(() => false);

function isPublicPortalUrl(url: string): boolean {
  // Use exact suffix checks to avoid substring collisions
  // e.g. '/portal/auth/logout' must NOT match '/portal/auth/logout-all'
  const publicSuffixes = [
    '/portal/settings',
    '/portal/shops',
    '/portal/track',
    '/portal/auth/register',
    '/portal/auth/login',
    '/portal/auth/refresh',
    '/portal/auth/logout',        // single-session logout (no token needed)
  ];
  const publicPrefixes = [
    '/portal/auth/password/',     // password reset request + confirm
  ];

  // Normalise to path-only (strip query / hash)
  const path = url.split('?')[0].split('#')[0];

  return (
    publicSuffixes.some((s) => path.endsWith(s)) ||
    publicPrefixes.some((p) => path.includes(p))
  );
}

export const portalAuthInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.context.get(PORTAL_SKIP_AUTH)) {
    return next(req);
  }

  const tokens = inject(PortalTokenStore);
  const http = inject(HttpClient);

  let outgoing = req;
  const access = tokens.getAccessToken();
  if (!isPublicPortalUrl(req.url) && access) {
    outgoing = req.clone({
      setHeaders: { Authorization: `Bearer ${access}` },
    });
  }

  return next(outgoing).pipe(
    catchError((err: unknown) => {
      if (!(err instanceof HttpErrorResponse) || err.status !== 401) {
        return throwError(() => err);
      }
      if (req.url.includes('/portal/auth/refresh')) {
        return throwError(() => err);
      }

      const refresh = tokens.getRefreshToken();
      if (!refresh) {
        return throwError(() => err);
      }

      return http
        .post<PortalAuthResponse>(
          `${environment.apiUrl}/portal/auth/refresh`,
          { refresh_token: refresh },
          { context: new HttpContext().set(PORTAL_SKIP_AUTH, true) },
        )
        .pipe(
          switchMap((body) => {
            tokens.setTokens(body.access_token, body.refresh_token ?? refresh);
            const retryAccess = tokens.getAccessToken();
            return next(
              req.clone({
                setHeaders: retryAccess ? { Authorization: `Bearer ${retryAccess}` } : {},
              }),
            );
          }),
          catchError((refreshErr) => throwError(() => refreshErr)),
        );
    }),
  );
};
