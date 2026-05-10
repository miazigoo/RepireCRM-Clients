import * as L from 'leaflet';
import { CommonModule } from '@angular/common';
import {
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  inject
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import { Subject, takeUntil } from 'rxjs';

import {
  ClientPortalService,
  PortalPublicLocation,
  PortalSettings
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
    MatSelectModule
  ],
  templateUrl: './portal-landing.component.html',
  styleUrl: './portal-landing.component.scss'
})
export class PortalLandingComponent implements OnInit, OnDestroy {
  private readonly portal = inject(ClientPortalService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroy$ = new Subject<void>();

  settings: PortalSettings | null = null;
  loading = true;
  loadError = false;
  selectedCity = '';
  cityOptions: string[] = [];

  private map: L.Map | null = null;
  private markers: L.Layer[] = [];

  ngOnInit(): void {
    this.portal
      .settings()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (s) => {
          this.settings = s;
          this.buildCityList();
          this.loading = false;
          setTimeout(() => this.ensureMap(), 0);
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadError = true;
          this.loading = false;
        }
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

  get filteredLocations(): PortalPublicLocation[] {
    const all = this.settings?.locations ?? [];
    if (!this.selectedCity) return all;
    return all.filter((l) => (l.city || '').trim() === this.selectedCity);
  }

  private buildCityList(): void {
    const uniq = new Set<string>();
    for (const loc of this.settings?.locations ?? []) {
      const c = (loc.city || '').trim();
      if (c) uniq.add(c);
    }
    this.cityOptions = Array.from(uniq).sort((a, b) => a.localeCompare(b, 'ru'));
  }

  onCitySelect(value: string): void {
    this.selectedCity = value;
    void this.refreshMapMarkers();
  }

  routeUrl(loc: PortalPublicLocation): string {
    const t = loc.address || loc.name;
    return `https://yandex.ru/maps/?text=${encodeURIComponent(t)}`;
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
      iconAnchor: [12, 41]
    });

    this.map = L.map('landing-map', { center: [55.76, 37.64], zoom: 10 });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19
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
      this.cdr.markForCheck();
      return;
    }

    const latLngs: L.LatLng[] = [];

    for (const loc of locs) {
      let lat = loc.lat ?? undefined;
      let lng = loc.lng ?? undefined;
      if (lat == null || lng == null) {
        if (loc.address) {
          const pair = await this.geocodeAddress(loc.address);
          if (pair) {
            lat = pair[0];
            lng = pair[1];
          }
          await new Promise((r) => setTimeout(r, 1100));
        }
      }
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
      const bounds = L.latLngBounds(latLngs);
      this.map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
    }
    this.cdr.markForCheck();
  }

  private escapeHtml(s: string): string {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  private async geocodeAddress(address: string): Promise<[number, number] | null> {
    const q = address.trim();
    if (!q) return null;
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`;
      const r = await fetch(url, { headers: { Accept: 'application/json' } });
      const data = (await r.json()) as { lat?: string; lon?: string }[];
      if (data?.[0]?.lat && data?.[0]?.lon) {
        return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
      }
    } catch {
      /* ignore */
    }
    return null;
  }
}
