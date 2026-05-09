import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, map, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { PortalTokenStore } from '../portal-token.store';

export type AuthPolicy = 'phone_or_email' | 'phone_only' | 'email_only';
export type ContactType = 'phone' | 'email';

export interface PortalBanner {
  title: string;
  subtitle: string;
  image_url?: string | null;
  link_url?: string | null;
  active: boolean;
}

export interface PortalPromotion {
  crm_promotion_id: number;
  title: string;
  description: string;
  discount_type: string;
  value: string;
  max_discount_amount?: string | null;
  min_order_amount: string;
  starts_at?: string | null;
  ends_at?: string | null;
  promo_codes: string[];
  auto_apply: boolean;
}

export interface PortalMarketing {
  promotions: PortalPromotion[];
  banner: PortalBanner | null;
}

export interface PortalSettings {
  brand: {
    name: string;
    accent_color: string;
    logo_url?: string | null;
    support_phone?: string | null;
    support_email?: string | null;
  };
  auth: {
    policy: AuthPolicy;
    allow_phone: boolean;
    allow_email: boolean;
    require_verified_contact_for_orders: boolean;
  };
  marketing: PortalMarketing;
  features: Record<string, boolean>;
}

export interface PortalContact {
  id: number;
  type: ContactType;
  value: string;
  normalized_value: string;
  is_primary: boolean;
  verified_at?: string | null;
}

export interface PortalCustomer {
  id: number;
  first_name: string;
  last_name: string;
  middle_name?: string | null;
  phone?: string | null;
  email?: string | null;
  marketing_consent: boolean;
  contacts: PortalContact[];
}

export interface PortalRegisterRequest {
  first_name: string;
  last_name: string;
  middle_name?: string | null;
  phone?: string | null;
  email?: string | null;
  password: string;
  marketing_consent: boolean;
}

export interface PortalLoginRequest {
  identifier: string;
  password: string;
}

export interface PortalAuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string | null;
  customer: PortalCustomer;
}

export interface ChallengeResponse {
  message: string;
  delivery_id?: number | null;
  debug_code?: string | null;
}

export interface PortalShop {
  crm_shop_id?: number | null;
  code?: string | null;
  name?: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
}

export interface PortalOrganization {
  crm_organization_id?: number | null;
  name?: string;
}

export interface PortalDeviceDetail {
  device_type?: string | null;
  brand?: string | null;
  model_name?: string | null;
  serial_number?: string | null;
  imei?: string | null;
  color?: string | null;
  storage_capacity?: string | null;
}

export interface PortalWarranty {
  warranty_days?: number | null;
  warranty_until?: string | null;
  warranty_active?: boolean;
  is_warranty_case?: boolean;
  warranty_parent_order_id?: number | null;
  warranty_parent_order_number?: string | null;
  warranty_reason?: string | null;
}

export interface PortalAdditionalService {
  name: string;
  category?: string | null;
  quantity?: number;
  price?: number | null;
  total_price?: number | null;
}

export interface PortalPayment {
  crm_payment_id?: number | null;
  payment_number: string;
  payment_type: string;
  status: string;
  status_display: string;
  amount?: number | null;
  payment_method: string;
  payment_date?: string | null;
}

export interface PortalOrder {
  id: number;
  order_number: string;
  status: PortalOrderStatus;
  status_display: string;
  priority: string;
  device_title: string;
  problem_description: string;
  diagnosis?: string | null;
  work_description?: string | null;
  cost_estimate: number;
  final_cost?: number | null;
  remaining_payment: number;
  created_at: string;
  updated_at: string;
  estimated_completion?: string | null;
  repair_stages: PortalRepairStage[];
  approvals: PortalApproval[];
  organization?: PortalOrganization | null;
  shop?: PortalShop | null;
  device?: PortalDeviceDetail | null;
  warranty?: PortalWarranty | null;
  additional_services?: PortalAdditionalService[];
  payments?: PortalPayment[];
  accessories?: string | null;
  device_condition?: string | null;
  prepayment?: number | null;
  subtotal_before_discount?: number | null;
  discount_total?: number | null;
  total_cost?: number | null;
  completed_at?: string | null;
}

export type PortalOrderStatus =
  | 'received'
  | 'diagnosed'
  | 'waiting_parts'
  | 'in_repair'
  | 'testing'
  | 'ready'
  | 'completed'
  | 'cancelled'
  | string;

export interface PortalRepairStage {
  id: number | string;
  title: string;
  description?: string | null;
  photo_url?: string | null;
  created_at: string;
}

export interface PortalApproval {
  id: number | string;
  title: string;
  description?: string | null;
  amount: number;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled' | string;
  status_display: string;
  customer_comment?: string | null;
  decided_at?: string | null;
  created_at: string;
}

export interface PortalOrderCreate {
  device_type: string;
  brand: string;
  model_name: string;
  problem_description: string;
  serial_number?: string;
  imei?: string;
  color?: string;
  storage_capacity?: string;
  accessories?: string;
  device_condition?: string;
  cost_estimate: number;
}

@Injectable({
  providedIn: 'root',
})
export class ClientPortalService {
  private readonly baseUrl = `${environment.apiUrl}/portal`;
  private readonly customerKey = 'portal_customer';
  private readonly customerSubject = new BehaviorSubject<PortalCustomer | null>(null);

  readonly customer$ = this.customerSubject.asObservable();

  constructor(
    private readonly http: HttpClient,
    private readonly tokens: PortalTokenStore,
  ) {
    this.restoreSession();
  }

  settings(): Observable<PortalSettings> {
    return this.http.get<PortalSettings>(`${this.baseUrl}/settings`);
  }

  register(data: PortalRegisterRequest): Observable<PortalAuthResponse> {
    return this.http.post<PortalAuthResponse>(`${this.baseUrl}/auth/register`, this.cleanPayload(data)).pipe(
      tap((response) => this.saveSession(response)),
    );
  }

  login(data: PortalLoginRequest): Observable<PortalAuthResponse> {
    return this.http.post<PortalAuthResponse>(`${this.baseUrl}/auth/login`, this.cleanPayload(data)).pipe(
      tap((response) => this.saveSession(response)),
    );
  }

  requestPasswordReset(identifier: string): Observable<ChallengeResponse> {
    return this.http.post<ChallengeResponse>(`${this.baseUrl}/auth/password/request-reset`, { identifier });
  }

  confirmPasswordReset(identifier: string, code: string, newPassword: string): Observable<ChallengeResponse> {
    return this.http.post<ChallengeResponse>(`${this.baseUrl}/auth/password/confirm-reset`, {
      identifier,
      code,
      new_password: newPassword,
    });
  }

  logout(): void {
    const refresh = this.tokens.getRefreshToken();
    this.tokens.clear();
    localStorage.removeItem(this.customerKey);
    this.customerSubject.next(null);
    if (refresh) {
      this.http.post(`${this.baseUrl}/auth/logout`, { refresh_token: refresh }).subscribe({ error: () => undefined });
    }
  }

  logoutAllSessions(): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/auth/logout-all`, {}).pipe(
      tap(() => {
        this.tokens.clear();
        localStorage.removeItem(this.customerKey);
        this.customerSubject.next(null);
      }),
    );
  }

  me(): Observable<PortalCustomer> {
    return this.http.get<PortalCustomer>(`${this.baseUrl}/me`).pipe(tap((customer) => this.saveCustomer(customer)));
  }

  updateProfile(data: Partial<PortalCustomer>): Observable<PortalCustomer> {
    return this.http.patch<PortalCustomer>(`${this.baseUrl}/me`, this.cleanPayload(data)).pipe(
      tap((customer) => this.saveCustomer(customer)),
    );
  }

  addContact(type: ContactType, value: string): Observable<ChallengeResponse> {
    return this.http.post<ChallengeResponse>(`${this.baseUrl}/me/contacts`, {
      type,
      value,
      make_primary: true,
    });
  }

  requestContactVerification(type: ContactType, value: string): Observable<ChallengeResponse> {
    return this.http.post<ChallengeResponse>(`${this.baseUrl}/me/contacts/request-verification`, { type, value });
  }

  confirmContact(type: ContactType, value: string, code: string): Observable<PortalCustomer> {
    return this.http
      .post<PortalCustomer>(`${this.baseUrl}/me/contacts/confirm`, { type, value, code })
      .pipe(tap((customer) => this.saveCustomer(customer)));
  }

  orders(): Observable<PortalOrder[]> {
    return this.http.get<{ items: PortalOrder[]; total: number; limit: number; offset: number }>(
      `${this.baseUrl}/orders`
    ).pipe(map(page => page.items));
  }

  order(orderId: number): Observable<PortalOrder> {
    return this.http.get<PortalOrder>(`${this.baseUrl}/orders/${orderId}`);
  }

  createOrder(data: PortalOrderCreate): Observable<PortalOrder> {
    return this.http.post<PortalOrder>(`${this.baseUrl}/orders`, this.cleanPayload(data));
  }

  approveApproval(id: number | string, comment = ''): Observable<PortalApproval> {
    return this.http.post<PortalApproval>(`${this.baseUrl}/approvals/${id}/approve`, { comment });
  }

  rejectApproval(id: number | string, comment = ''): Observable<PortalApproval> {
    return this.http.post<PortalApproval>(`${this.baseUrl}/approvals/${id}/reject`, { comment });
  }

  trackOrder(data: { order_number: string; phone?: string; email?: string }): Observable<PortalOrder> {
    return this.http.post<PortalOrder>(`${this.baseUrl}/track`, this.cleanPayload(data));
  }

  isAuthenticated(): boolean {
    return Boolean(this.tokens.getAccessToken());
  }

  private saveSession(response: PortalAuthResponse): void {
    this.tokens.setTokens(response.access_token, response.refresh_token ?? undefined);
    this.saveCustomer(response.customer);
  }

  private saveCustomer(customer: PortalCustomer): void {
    localStorage.setItem(this.customerKey, JSON.stringify(customer));
    this.customerSubject.next(customer);
  }

  private restoreSession(): void {
    const savedCustomer = localStorage.getItem(this.customerKey);
    if (!savedCustomer) {
      return;
    }

    try {
      this.customerSubject.next(JSON.parse(savedCustomer) as PortalCustomer);
    } catch {
      this.logout();
    }
  }

  private cleanPayload<T extends object>(data: T): T {
    return Object.entries(data).reduce((payload, [key, value]) => {
      if (typeof value === 'string') {
        const trimmed = value.trim();
        if (trimmed) {
          payload[key as keyof T] = trimmed as T[keyof T];
        }
        return payload;
      }
      if (value !== null && value !== undefined) {
        payload[key as keyof T] = value as T[keyof T];
      }
      return payload;
    }, {} as T);
  }
}
