import * as L from 'leaflet';
import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnDestroy, OnInit, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import { forkJoin, of, Subject, takeUntil } from 'rxjs';
import { catchError } from 'rxjs/operators';

import {
  ClientPortalService,
  PortalLandingFeatureCard,
  PortalLandingPromoSpotlight,
  PortalPublicLocation,
  PortalSettings,
} from '../../services/client-portal.service';

@Component({
  selector: 'app-portal-landing',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  templateUrl: './portal-landing.component.html',
  styleUrl: './portal-landing.component.scss',
})
export class PortalLandingComponent implements OnInit, OnDestroy {
  private readonly defaultFeatureCards: PortalLandingFeatureCard[] = [
    {
      title: 'Статус ремонта',
      body: 'Диагностика, запчасти, ремонт и готовность — в одной ленте, без догадок.',
      icon: 'status',
    },
    {
      title: 'Смета до оплаты',
      body: 'Согласуйте допработы в пару кликов — суммы и детали всегда перед глазами.',
      icon: 'pricing',
    },
    {
      title: 'Сервисы на карте',
      body: 'Точки приёма и маршрут во внешних картах — вы выбираете, как добраться.',
      icon: 'map',
    },
  ];

  private readonly defaultSectionEyebrow = 'Почему с нами спокойно';
  private readonly defaultSectionTitle = 'Под контролем — как часы';
  private readonly defaultSectionSubtitle =
    'Кабинет клиента держит вас в курсе процесса: видно сроки, смету и статус без звонков в сервис.';

  private readonly portal = inject(ClientPortalService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroy$ = new Subject<void>();

  settings: PortalSettings | null = null;
  /** Точки для карты и фильтра городов (из /portal/shops). */
  mapLocations: PortalPublicLocation[] = [];
  loading = true;
  loadError = false;
  selectedCity = '';
  cityOptions: string[] = [];

  private userGeo: { lat: number; lng: number } | null = null;

  private map: L.Map | null = null;
  private markers: L.Layer[] = [];

  ngOnInit(): void {
    this.requestUserGeolocation();
    forkJoin({
      settings: this.portal.settings(),
      shops: this.portal.publicShops().pipe(catchError(() => of([] as PortalPublicLocation[]))),
    })
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: ({ settings, shops }) => {
          this.settings = settings;
          this.mapLocations = shops;
          this.buildCityList();
          this.loading = false;
          setTimeout(() => this.ensureMap(), 0);
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadError = true;
          this.loading = false;
        },
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.map?.remove();
    this.map = null;
  }

  get brandName(): string {
    return this.settings?.brand?.name?.trim() || 'Сервисный центр';
  }

  get accentColor(): string {
    return this.settings?.brand?.accent_color?.trim() || '#0d9488';
  }

  get displayFeatureCards(): PortalLandingFeatureCard[] {
    const raw = this.settings?.landing?.feature_cards ?? [];
    const filled = raw.filter((c) => (c.title || '').trim() && (c.body || '').trim());
    if (filled.length > 0) {
      return filled;
    }
    return this.defaultFeatureCards;
  }

  get landingSectionEyebrow(): string {
    const t = (this.settings?.landing?.section_eyebrow || '').trim();
    return t || this.defaultSectionEyebrow;
  }

  get landingSectionTitle(): string {
    const t = (this.settings?.landing?.section_title || '').trim();
    return t || this.defaultSectionTitle;
  }

  get landingSectionSubtitle(): string {
    const t = (this.settings?.landing?.section_subtitle || '').trim();
    return t || this.defaultSectionSubtitle;
  }

  get landingPromo(): PortalLandingPromoSpotlight | null {
    const p = this.settings?.landing?.promo_spotlight;
    if (!p?.enabled) return null;
    if (!(p.title?.trim() || p.body?.trim())) return null;
    return p;
  }

  get promoCtaHref(): string {
    const p = this.settings?.landing?.promo_spotlight;
    const h = (p?.cta_href || '').trim();
    return h || '/login';
  }

  get promoCtaLabel(): string {
    const p = this.settings?.landing?.promo_spotlight;
    return (p?.cta_label || '').trim() || 'Подробнее';
  }

  get promoCtaIsExternal(): boolean {
    const h = this.promoCtaHref;
    return h.startsWith('http://') || h.startsWith('https://');
  }

  get filteredLocations(): PortalPublicLocation[] {
    const all = this.mapLocations;
    if (!this.selectedCity) return all;
    return all.filter((l) => (l.city || '').trim() === this.selectedCity);
  }

  get cityFilters(): Array<{ city: string; count: number }> {
    return this.cityOptions.map((city) => ({
      city,
      count: this.mapLocations.filter((loc) => (loc.city || '').trim() === city).length,
    }));
  }

  private buildCityList(): void {
    const uniq = new Set<string>();
    for (const loc of this.mapLocations) {
      const c = (loc.city || '').trim();
      if (c) uniq.add(c);
    }
    this.cityOptions = Array.from(uniq).sort((a, b) => a.localeCompare(b, 'ru'));
  }

  private requestUserGeolocation(): void {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.userGeo = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        void this.refreshMapMarkers();
        this.cdr.markForCheck();
      },
      () => undefined,
      { enableHighAccuracy: false, timeout: 9000, maximumAge: 300_000 },
    );
  }

  onCitySelect(value: string): void {
    this.selectedCity = value;
    void this.refreshMapMarkers();
  }

  routeUrl(loc: PortalPublicLocation): string {
    const title = [loc.name, loc.address].filter(Boolean).join(', ');
    const lat = this.toFiniteCoord(loc.lat);
    const lng = this.toFiniteCoord(loc.lng);
    if (lat != null && lng != null) {
      return `https://yandex.ru/maps/?ll=${lng},${lat}&z=16&text=${encodeURIComponent(title)}`;
    }
    return `https://yandex.ru/maps/?text=${encodeURIComponent(title || loc.name)}`;
  }

  telHref(phone: string | undefined | null): string {
    const p = (phone || '').replace(/\s+/g, '');
    return p ? `tel:${p}` : '';
  }

  private ensureMap(): void {
    if (this.map) {
      void this.refreshMapMarkers();
      return;
    }
    const el = document.getElementById('landing-map');
    if (!el) return;

    L.Marker.prototype.options.icon = L.icon({
      iconUrl: 'assets/leaflet/marker-icon.png',
      iconRetinaUrl: 'assets/leaflet/marker-icon-2x.png',
      shadowUrl: 'assets/leaflet/marker-shadow.png',
      iconSize: [25, 41],
      iconAnchor: [12, 41],
    });

    this.map = L.map('landing-map', { center: [55.76, 37.64], zoom: 10 });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(this.map);

    void this.refreshMapMarkers();
  }

  private async refreshMapMarkers(): Promise<void> {
    if (!this.map) return;
    for (const m of this.markers) {
      this.map.removeLayer(m);
    }
    this.markers = [];
    const locs = this.filteredLocations;
    if (locs.length === 0) {
      if (this.userGeo) {
        this.map.setView(L.latLng(this.userGeo.lat, this.userGeo.lng), 10);
      } else {
        this.map.setView(L.latLng(55.76, 37.64), 10);
      }
      this.map.invalidateSize();
      this.cdr.markForCheck();
      return;
    }

    const latLngs: L.LatLng[] = [];

    for (const loc of locs) {
      const lat = this.toFiniteCoord(loc.lat);
      const lng = this.toFiniteCoord(loc.lng);
      if (lat == null || lng == null) continue;
      const ll = L.latLng(lat, lng);
      latLngs.push(ll);
      const routeUrl = this.routeUrl(loc);
      const popupHtml =
        `<strong>${this.escapeHtml(loc.name)}</strong><br>` +
        `${this.escapeHtml(loc.address || '')}<br>` +
        `<a href="${routeUrl}" target="_blank" rel="noopener">Маршрут в Яндекс Картах →</a>`;
      const marker = L.marker(ll).bindPopup(popupHtml);
      marker.addTo(this.map);
      this.markers.push(marker);
    }

    if (latLngs.length > 0) {
      let bounds = L.latLngBounds(latLngs);
      if (this.userGeo) {
        bounds = bounds.extend(L.latLng(this.userGeo.lat, this.userGeo.lng));
      }
      this.map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
    }
    this.map.invalidateSize();
    this.cdr.markForCheck();
  }

  private toFiniteCoord(value: number | string | null | undefined): number | null {
    if (value == null || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  private escapeHtml(s: string): string {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}
