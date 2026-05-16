import { DOCUMENT, isPlatformBrowser } from '@angular/common';
import { Injectable, PLATFORM_ID, inject } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

import { environment } from '../../environments/environment';

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: AnalyticsFn;
    ym?: AnalyticsFn;
    __REPIRECRM_CLIENT_CONFIG__?: {
      publicSiteUrl?: string;
      googleTagId?: string;
      yandexMetrikaId?: string;
    };
  }
}

type AnalyticsFn = ((...args: unknown[]) => void) & { a?: unknown[] };

@Injectable({
  providedIn: 'root',
})
export class AnalyticsService {
  private readonly document = inject(DOCUMENT);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly router = inject(Router);
  private initialized = false;

  init(): void {
    if (this.initialized || !isPlatformBrowser(this.platformId)) return;
    this.initialized = true;

    this.captureAttribution();
    this.initGoogle();
    this.initYandex();
    this.trackPageView();

    this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe(() => {
      this.trackPageView();
    });
  }

  trackEvent(name: string, params: Record<string, unknown> = {}): void {
    const eventName = this.normalizeEventName(name);
    window.gtag?.('event', eventName, params);
    const yandexId = this.yandexMetrikaId;
    if (yandexId) {
      window.ym?.(Number(yandexId), 'reachGoal', eventName, params);
    }
  }

  private initGoogle(): void {
    const id = this.googleTagId;
    if (!id) return;

    window.dataLayer = window.dataLayer || [];
    window.gtag =
      window.gtag ||
      function gtag(...args: unknown[]) {
        window.dataLayer?.push(args);
      };
    window.gtag('js', new Date());
    window.gtag('config', id, { send_page_view: false });
    this.addScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`);
  }

  private initYandex(): void {
    const id = this.yandexMetrikaId;
    if (!id) return;

    window.ym =
      window.ym ||
      function ym(...args: unknown[]) {
        window.ym!.a = window.ym!.a || [];
        window.ym!.a.push(args);
      };
    window.ym(Number(id), 'init', {
      clickmap: true,
      trackLinks: true,
      accurateTrackBounce: true,
      webvisor: false,
    });
    this.addScript('https://mc.yandex.ru/metrika/tag.js');
  }

  private trackPageView(): void {
    const path = window.location.pathname + window.location.search;
    const googleId = this.googleTagId;
    const yandexId = this.yandexMetrikaId;
    if (googleId) {
      window.gtag?.('config', googleId, { page_path: path });
    }
    if (yandexId) {
      window.ym?.(Number(yandexId), 'hit', path);
    }
  }

  private get googleTagId(): string {
    return (
      window.__REPIRECRM_CLIENT_CONFIG__?.googleTagId?.trim() ||
      environment.analytics.googleTagId?.trim() ||
      ''
    );
  }

  private get yandexMetrikaId(): string {
    return (
      window.__REPIRECRM_CLIENT_CONFIG__?.yandexMetrikaId?.trim() ||
      environment.analytics.yandexMetrikaId?.trim() ||
      ''
    );
  }

  private captureAttribution(): void {
    const params = new URLSearchParams(window.location.search);
    const keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'yclid'];
    const data: Record<string, string> = {};
    for (const key of keys) {
      const value = params.get(key);
      if (value) data[key] = value.slice(0, 300);
    }
    if (Object.keys(data).length > 0) {
      sessionStorage.setItem('repirecrm_landing_attribution', JSON.stringify(data));
    }
  }

  private addScript(src: string): void {
    if (this.document.querySelector(`script[src="${src}"]`)) return;
    const script = this.document.createElement('script');
    script.async = true;
    script.src = src;
    this.document.head.appendChild(script);
  }

  private normalizeEventName(name: string): string {
    return name.replace(/[^a-zA-Z0-9_]/g, '_').slice(0, 80);
  }
}
