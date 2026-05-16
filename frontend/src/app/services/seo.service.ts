import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

import { environment } from '../../environments/environment';
import { PortalPublicLocation, PortalSettings } from './client-portal.service';

declare global {
  interface Window {
    __REPIRECRM_CLIENT_CONFIG__?: {
      publicSiteUrl?: string;
      googleTagId?: string;
      yandexMetrikaId?: string;
    };
  }
}

@Injectable({
  providedIn: 'root',
})
export class SeoService {
  private readonly title = inject(Title);
  private readonly meta = inject(Meta);
  private readonly document = inject(DOCUMENT);

  setLanding(settings: PortalSettings, locations: PortalPublicLocation[]): void {
    const brandName = settings.brand.name?.trim() || 'Сервисный центр';
    const cities = this.uniqueCities(locations);
    const cityText = cities.length === 1 ? ` в ${cities[0]}` : '';
    const title = `${brandName} — ремонт техники и статус ремонта онлайн${cityText}`;
    const description = this.clip(
      [
        `${brandName}: ремонт техники${cityText}, онлайн-заявки и личный кабинет клиента.`,
        'Проверяйте статус ремонта, согласовывайте работы и находите ближайшую сервисную точку.',
      ].join(' '),
      160,
    );
    const canonical = this.absoluteUrl('/');
    const image = this.absoluteUrl(
      settings.landing?.promo_spotlight?.image_url ||
        settings.brand.logo_url ||
        'assets/landing/hero-illustration.svg',
    );

    this.title.setTitle(title);
    this.setTag('description', description);
    this.setTag('robots', 'index, follow, max-image-preview:large');
    this.setTag('theme-color', settings.brand.accent_color || '#0f172a');
    this.setCanonical(canonical);

    this.setProperty('og:locale', 'ru_RU');
    this.setProperty('og:type', 'website');
    this.setProperty('og:site_name', brandName);
    this.setProperty('og:title', title);
    this.setProperty('og:description', description);
    this.setProperty('og:url', canonical);
    this.setProperty('og:image', image);
    this.setTag('twitter:card', 'summary_large_image');
    this.setTag('twitter:title', title);
    this.setTag('twitter:description', description);
    this.setTag('twitter:image', image);

    this.setSchema(this.landingSchema(settings, locations, canonical, image));
  }

  setPrivatePortalPage(brandName = 'Repair CRM'): void {
    this.title.setTitle(`Личный кабинет — ${brandName}`);
    this.setTag('description', 'Личный кабинет клиента: статусы ремонта, согласования и заявки онлайн.');
    this.setTag('robots', 'noindex, nofollow');
    this.setCanonical(this.absoluteUrl('/login'));
    this.removeSchema();
  }

  private landingSchema(
    settings: PortalSettings,
    locations: PortalPublicLocation[],
    canonical: string,
    image: string,
  ): Record<string, unknown> {
    const brandName = settings.brand.name?.trim() || 'Сервисный центр';
    const departments = locations
      .filter((loc) => loc.name?.trim() || loc.address?.trim())
      .slice(0, 20)
      .map((loc) => ({
        '@type': 'LocalBusiness',
        name: loc.name || brandName,
        telephone: loc.phone || settings.brand.support_phone || undefined,
        email: loc.email || settings.brand.support_email || undefined,
        address: loc.address
          ? {
              '@type': 'PostalAddress',
              streetAddress: loc.address,
              addressLocality: loc.city || undefined,
              addressCountry: 'RU',
            }
          : undefined,
        geo:
          loc.lat != null && loc.lng != null
            ? {
                '@type': 'GeoCoordinates',
                latitude: loc.lat,
                longitude: loc.lng,
              }
            : undefined,
      }));

    const offers = [
      ...(settings.marketing?.promotions || []).slice(0, 10).map((promo) => ({
        '@type': 'Offer',
        name: promo.title,
        description: promo.description || undefined,
        availability: 'https://schema.org/InStock',
      })),
      settings.field_visit?.enabled
        ? {
            '@type': 'Offer',
            name: settings.field_visit.service_name || 'Выезд мастера',
            description: settings.field_visit.description || undefined,
            priceCurrency: 'RUB',
            price: String(settings.field_visit.base_price || 0),
          }
        : null,
    ].filter(Boolean);

    return {
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'WebSite',
          '@id': `${canonical}#website`,
          url: canonical,
          name: brandName,
          inLanguage: 'ru-RU',
        },
        {
          '@type': 'LocalBusiness',
          '@id': `${canonical}#business`,
          name: brandName,
          url: canonical,
          image,
          logo: settings.brand.logo_url ? this.absoluteUrl(settings.brand.logo_url) : undefined,
          telephone: settings.brand.support_phone || undefined,
          email: settings.brand.support_email || undefined,
          priceRange: '₽₽',
          areaServed: this.uniqueCities(locations),
          department: departments.length ? departments : undefined,
        },
        offers.length
          ? {
              '@type': 'OfferCatalog',
              '@id': `${canonical}#offers`,
              name: `Акции и услуги ${brandName}`,
              itemListElement: offers,
            }
          : null,
      ].filter(Boolean),
    };
  }

  private uniqueCities(locations: PortalPublicLocation[]): string[] {
    return Array.from(new Set(locations.map((loc) => (loc.city || '').trim()).filter(Boolean))).sort(
      (a, b) => a.localeCompare(b, 'ru'),
    );
  }

  private absoluteUrl(value: string): string {
    const raw = (value || '/').trim();
    if (raw.startsWith('http://') || raw.startsWith('https://')) {
      return raw;
    }
    const configured =
      window.__REPIRECRM_CLIENT_CONFIG__?.publicSiteUrl?.trim() ||
      environment.publicSiteUrl?.trim();
    const origin =
      configured ||
      (typeof window !== 'undefined' && window.location?.origin ? window.location.origin : '');
    const path = raw.startsWith('/') ? raw : `/${raw}`;
    return `${origin}${path}`;
  }

  private setTag(name: string, content: string): void {
    this.meta.updateTag({ name, content });
  }

  private setProperty(property: string, content: string): void {
    this.meta.updateTag({ property, content });
  }

  private setCanonical(href: string): void {
    let link = this.document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = this.document.createElement('link');
      link.rel = 'canonical';
      this.document.head.appendChild(link);
    }
    link.href = href;
  }

  private setSchema(data: Record<string, unknown>): void {
    let el = this.document.getElementById('ld-json-main') as HTMLScriptElement | null;
    if (!el) {
      el = this.document.createElement('script');
      el.type = 'application/ld+json';
      el.id = 'ld-json-main';
      this.document.head.appendChild(el);
    }
    el.text = JSON.stringify(data);
  }

  private removeSchema(): void {
    this.document.getElementById('ld-json-main')?.remove();
  }

  private clip(value: string, max: number): string {
    const compact = value.replace(/\s+/g, ' ').trim();
    if (compact.length <= max) return compact;
    return `${compact.slice(0, max - 1).trim()}…`;
  }
}
