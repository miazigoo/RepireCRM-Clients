import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class PortalTokenStore {
  private readonly accessKey = 'portal_access_token';
  private readonly refreshKey = 'portal_refresh_token';

  getAccessToken(): string | null {
    return localStorage.getItem(this.accessKey);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(this.refreshKey);
  }

  setTokens(access: string, refresh: string | null | undefined): void {
    localStorage.setItem(this.accessKey, access);
    if (refresh) {
      localStorage.setItem(this.refreshKey, refresh);
    }
  }

  clear(): void {
    localStorage.removeItem(this.accessKey);
    localStorage.removeItem(this.refreshKey);
  }
}
