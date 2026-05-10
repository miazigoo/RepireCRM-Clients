import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subject, finalize, takeUntil } from 'rxjs';

import {
  AuthPolicy,
  ChallengeResponse,
  ClientPortalService,
  ContactType,
  PortalApproval,
  PortalBanner,
  PortalContact,
  PortalCustomer,
  PortalLoginRequest,
  PortalOrder,
  PortalOrderCreate,
  PortalPromotion,
  PortalRegisterRequest,
  PortalSettings
} from '../../services/client-portal.service';

type AuthMode = 'login' | 'register' | 'reset';
type LoadingAction =
  | 'settings'
  | 'login'
  | 'register'
  | 'reset'
  | 'track'
  | 'order'
  | 'session'
  | 'profile'
  | 'contact'
  | null;

interface StatusStep {
  key: string;
  label: string;
  icon: string;
}

@Component({
  selector: 'app-client-portal',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTabsModule,
    MatTooltipModule
  ],
  templateUrl: './client-portal.component.html',
  styleUrl: './client-portal.component.scss'
})
export class ClientPortalComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly portalService = inject(ClientPortalService);

  readonly deviceTypes = ['Телефон', 'Планшет', 'Ноутбук', 'Компьютер', 'Монитор', 'Другое'];
  readonly contactTypes: { value: ContactType; label: string }[] = [
    { value: 'phone', label: 'Телефон' },
    { value: 'email', label: 'Email' }
  ];

  readonly statusSteps: StatusStep[] = [
    { key: 'received', label: 'Принят', icon: 'inventory_2' },
    { key: 'diagnosed', label: 'Диагностика', icon: 'manage_search' },
    { key: 'waiting_parts', label: 'Запчасти', icon: 'hourglass_empty' },
    { key: 'in_repair', label: 'Ремонт', icon: 'build' },
    { key: 'testing', label: 'Проверка', icon: 'fact_check' },
    { key: 'ready', label: 'Готов', icon: 'task_alt' },
    { key: 'completed', label: 'Выдан', icon: 'verified' }
  ];

  settings: PortalSettings | null = null;
  customer: PortalCustomer | null = null;
  orders: PortalOrder[] = [];
  trackedOrder: PortalOrder | null = null;
  authMode: AuthMode = 'login';
  selectedTabIndex = 0;
  hidePassword = true;
  loadingAction: LoadingAction = null;
  ordersLoading = false;
  decisionLoadingId: number | string | null = null;
  error = '';
  success = '';
  resetDebugCode = '';
  contactDebugCode = '';
  approvalComments: Record<string, string> = {};

  loginForm: FormGroup;
  registerForm: FormGroup;
  resetRequestForm: FormGroup;
  resetConfirmForm: FormGroup;
  profileForm: FormGroup;
  contactForm: FormGroup;
  verifyContactForm: FormGroup;
  orderForm: FormGroup;
  trackForm: FormGroup;

  private readonly destroy$ = new Subject<void>();

  constructor() {
    this.loginForm = this.fb.group({
      identifier: ['', Validators.required],
      password: ['', [Validators.required, Validators.minLength(8)]]
    });

    this.registerForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      phone: [''],
      email: ['', Validators.email],
      password: ['', [Validators.required, Validators.minLength(8)]],
      marketing_consent: [true]
    });

    this.resetRequestForm = this.fb.group({
      identifier: ['', Validators.required]
    });

    this.resetConfirmForm = this.fb.group({
      identifier: ['', Validators.required],
      code: ['', Validators.required],
      new_password: ['', [Validators.required, Validators.minLength(8)]]
    });

    this.profileForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      middle_name: [''],
      marketing_consent: [false]
    });

    this.contactForm = this.fb.group({
      type: ['phone' satisfies ContactType, Validators.required],
      value: ['', Validators.required]
    });

    this.verifyContactForm = this.fb.group({
      type: ['phone' satisfies ContactType, Validators.required],
      value: ['', Validators.required],
      code: ['', Validators.required]
    });

    this.orderForm = this.fb.group({
      device_type: ['Телефон', Validators.required],
      brand: ['', Validators.required],
      model_name: ['', Validators.required],
      serial_number: [''],
      imei: ['', Validators.pattern(/^\d{14,15}$/)],
      color: [''],
      storage_capacity: [''],
      accessories: [''],
      device_condition: [''],
      problem_description: ['', [Validators.required, Validators.minLength(10)]],
      cost_estimate: [0, [Validators.required, Validators.min(0)]]
    });

    this.trackForm = this.fb.group({
      order_number: ['', Validators.required],
      contact: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    this.loadSettings();

    this.portalService.customer$
      .pipe(takeUntil(this.destroy$))
      .subscribe((customer) => {
        this.customer = customer;
        this.patchProfileForm(customer);

        if (customer) {
          this.loadOrders();
          return;
        }

        this.orders = [];
        this.selectedTabIndex = 0;
      });

    if (this.portalService.isAuthenticated()) {
      this.loadingAction = 'session';
      this.portalService.me()
        .pipe(
          finalize(() => (this.loadingAction = null)),
          takeUntil(this.destroy$)
        )
        .subscribe({
          error: () => {
            this.portalService.logout();
            this.error = 'Сессия истекла. Войдите снова.';
          }
        });
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  get brandName(): string {
    return this.settings?.brand.name || 'Repair CRM';
  }

  get authPolicy(): AuthPolicy {
    return this.settings?.auth.policy || 'phone_or_email';
  }

  get allowPhone(): boolean {
    return this.settings?.auth.allow_phone ?? true;
  }

  get allowEmail(): boolean {
    return this.settings?.auth.allow_email ?? true;
  }

  get loginLabel(): string {
    if (this.authPolicy === 'phone_only') {
      return 'Телефон';
    }
    if (this.authPolicy === 'email_only') {
      return 'Email';
    }
    return 'Телефон или email';
  }

  get customerName(): string {
    if (!this.customer) {
      return '';
    }

    return `${this.customer.first_name} ${this.customer.last_name}`.trim();
  }

  get contacts(): PortalContact[] {
    return this.customer?.contacts || [];
  }

  get activeOrdersCount(): number {
    return this.orders.filter((order) => !['completed', 'cancelled'].includes(order.status)).length;
  }

  get completedOrdersCount(): number {
    return this.orders.filter((order) => order.status === 'completed').length;
  }

  get pendingApprovalsCount(): number {
    return this.orders.reduce(
      (total, order) => total + order.approvals.filter((approval) => approval.status === 'pending').length,
      0
    );
  }

  get totalRemainingPayment(): number {
    return this.orders.reduce((total, order) => total + Number(order.remaining_payment || 0), 0);
  }

  get marketingBanner(): PortalBanner | null {
    const b = this.settings?.marketing?.banner;
    if (!b?.active) {
      return null;
    }
    const hasText = Boolean(b.title?.trim() || b.subtitle?.trim());
    const hasImage = Boolean(b.image_url?.trim());
    if (!hasText && !hasImage) {
      return null;
    }
    return b;
  }

  get marketingPromotions(): PortalPromotion[] {
    return this.settings?.marketing?.promotions ?? [];
  }

  get canSubmitRegister(): boolean {
    if (this.registerForm.invalid) {
      return false;
    }

    const value = this.registerForm.getRawValue();
    if (this.authPolicy === 'phone_only') {
      return Boolean(value.phone?.trim());
    }
    if (this.authPolicy === 'email_only') {
      return Boolean(value.email?.trim());
    }
    return Boolean(value.phone?.trim() || value.email?.trim());
  }

  get visibleContactTypes(): { value: ContactType; label: string }[] {
    return this.contactTypes.filter((type) => this.isContactTypeAllowed(type.value));
  }

  switchAuthMode(mode: AuthMode): void {
    this.authMode = mode;
    this.clearMessages();
  }

  login(): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.loadingAction = 'login';
    this.clearMessages();
    this.portalService.login(this.loginForm.getRawValue() as PortalLoginRequest)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: () => {
          this.success = 'Вы вошли в кабинет';
          this.selectedTabIndex = 0;
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  register(): void {
    if (!this.canSubmitRegister) {
      this.registerForm.markAllAsTouched();
      this.error = 'Укажите разрешенный контакт для регистрации';
      return;
    }

    const value = this.registerForm.getRawValue();
    const payload: PortalRegisterRequest = {
      first_name: value.first_name,
      last_name: value.last_name,
      phone: this.allowPhone ? value.phone || null : null,
      email: this.allowEmail ? value.email || null : null,
      password: value.password,
      marketing_consent: Boolean(value.marketing_consent)
    };

    this.loadingAction = 'register';
    this.clearMessages();
    this.portalService.register(payload)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: () => {
          this.success = 'Кабинет создан. Подтвердите контакт в профиле, чтобы увидеть связанные заказы.';
          this.selectedTabIndex = 3;
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  requestPasswordReset(): void {
    if (this.resetRequestForm.invalid) {
      this.resetRequestForm.markAllAsTouched();
      return;
    }

    const identifier = this.resetRequestForm.get('identifier')?.value;
    this.loadingAction = 'reset';
    this.resetDebugCode = '';
    this.clearMessages();
    this.portalService.requestPasswordReset(identifier)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: (response) => {
          this.resetConfirmForm.patchValue({ identifier });
          this.resetDebugCode = response.debug_code || '';
          this.success = response.message;
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  confirmPasswordReset(): void {
    if (this.resetConfirmForm.invalid) {
      this.resetConfirmForm.markAllAsTouched();
      return;
    }

    const value = this.resetConfirmForm.getRawValue();
    this.loadingAction = 'reset';
    this.clearMessages();
    this.portalService.confirmPasswordReset(value.identifier, value.code, value.new_password)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: () => {
          this.success = 'Пароль обновлен. Теперь можно войти.';
          this.authMode = 'login';
          this.loginForm.patchValue({ identifier: value.identifier, password: '' });
          this.resetRequestForm.reset();
          this.resetConfirmForm.reset();
          this.resetDebugCode = '';
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  submitOrder(): void {
    if (this.orderForm.invalid) {
      this.orderForm.markAllAsTouched();
      return;
    }

    const value = this.orderForm.getRawValue();
    const payload: PortalOrderCreate = {
      ...value,
      cost_estimate: Number(value.cost_estimate || 0)
    };

    this.loadingAction = 'order';
    this.clearMessages();
    this.portalService.createOrder(payload)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: (order) => {
          this.success = `Заявка ${order.order_number} принята`;
          this.resetOrderForm();
          this.selectedTabIndex = 0;
          this.loadOrders();
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  trackOrder(): void {
    if (this.trackForm.invalid) {
      this.trackForm.markAllAsTouched();
      return;
    }

    const value = this.trackForm.getRawValue();
    this.loadingAction = 'track';
    this.trackedOrder = null;
    this.clearMessages();
    this.portalService.trackOrder({
      order_number: value.order_number,
      ...this.contactPayload(value.contact)
    }).pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: (order) => (this.trackedOrder = order),
        error: (error) => (this.error = this.extractError(error))
      });
  }

  loadOrders(): void {
    if (!this.customer) {
      return;
    }

    this.ordersLoading = true;
    this.portalService.orders()
      .pipe(finalize(() => (this.ordersLoading = false)))
      .subscribe({
        next: (orders) => (this.orders = orders),
        error: (error) => (this.error = this.extractError(error))
      });
  }

  updateProfile(): void {
    if (this.profileForm.invalid) {
      this.profileForm.markAllAsTouched();
      return;
    }

    this.loadingAction = 'profile';
    this.clearMessages();
    this.portalService.updateProfile(this.profileForm.getRawValue())
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: () => (this.success = 'Профиль обновлен'),
        error: (error) => (this.error = this.extractError(error))
      });
  }

  addContact(): void {
    if (this.contactForm.invalid) {
      this.contactForm.markAllAsTouched();
      return;
    }

    const value = this.contactForm.getRawValue() as { type: ContactType; value: string };
    this.loadingAction = 'contact';
    this.contactDebugCode = '';
    this.clearMessages();
    this.portalService.addContact(value.type, value.value)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: (response) => {
          this.handleContactChallenge(response);
          this.verifyContactForm.patchValue(value);
          this.contactForm.patchValue({ value: '' });
          this.portalService.me().subscribe();
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  requestContactVerification(contact: PortalContact): void {
    this.loadingAction = 'contact';
    this.contactDebugCode = '';
    this.clearMessages();
    this.portalService.requestContactVerification(contact.type, contact.value)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: (response) => {
          this.handleContactChallenge(response);
          this.verifyContactForm.patchValue({ type: contact.type, value: contact.value, code: '' });
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  confirmContact(): void {
    if (this.verifyContactForm.invalid) {
      this.verifyContactForm.markAllAsTouched();
      return;
    }

    const value = this.verifyContactForm.getRawValue() as { type: ContactType; value: string; code: string };
    this.loadingAction = 'contact';
    this.clearMessages();
    this.portalService.confirmContact(value.type, value.value, value.code)
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: () => {
          this.success = 'Контакт подтвержден';
          this.contactDebugCode = '';
          this.verifyContactForm.patchValue({ code: '' });
          this.loadOrders();
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  decideApproval(approval: PortalApproval, approve: boolean): void {
    if (this.decisionLoadingId) {
      return;
    }

    this.decisionLoadingId = approval.id;
    this.clearMessages();
    const key = String(approval.id);
    const comment = this.approvalComments[key]?.trim() || '';
    const request = approve
      ? this.portalService.approveApproval(approval.id, comment)
      : this.portalService.rejectApproval(approval.id, comment);

    request
      .pipe(finalize(() => (this.decisionLoadingId = null)))
      .subscribe({
        next: () => {
          delete this.approvalComments[key];
          this.success = approve ? 'Согласование принято' : 'Согласование отклонено';
          this.loadOrders();
        },
        error: (error) => (this.error = this.extractError(error))
      });
  }

  logout(): void {
    this.portalService.logout();
    this.trackedOrder = null;
    this.clearMessages();
  }

  setApprovalComment(approvalId: number | string, event: Event): void {
    const input = event.target as HTMLTextAreaElement;
    this.approvalComments[String(approvalId)] = input.value;
  }

  orderAmount(order: PortalOrder): number {
    return Number(order.final_cost ?? order.cost_estimate ?? 0);
  }

  hasOrderFinancialExtras(order: PortalOrder): boolean {
    const prepay = order.prepayment != null && order.prepayment > 0;
    const disc = order.discount_total != null && order.discount_total > 0;
    const total = order.total_cost != null;
    return Boolean(prepay || disc || total);
  }

  statusClass(status: string): string {
    return `status-${status.replaceAll('_', '-')}`;
  }

  approvalStatusClass(approval: PortalApproval): string {
    return `approval-${approval.status}`;
  }

  isPendingApproval(approval: PortalApproval): boolean {
    return approval.status === 'pending';
  }

  isVerified(contact: PortalContact): boolean {
    return Boolean(contact.verified_at);
  }

  contactLabel(contact: PortalContact): string {
    return contact.type === 'phone' ? 'Телефон' : 'Email';
  }

  isStepDone(orderStatus: string, stepKey: string): boolean {
    if (orderStatus === 'cancelled') {
      return false;
    }

    const currentIndex = this.statusSteps.findIndex((step) => step.key === orderStatus);
    const stepIndex = this.statusSteps.findIndex((step) => step.key === stepKey);
    return currentIndex >= 0 && stepIndex >= 0 && stepIndex <= currentIndex;
  }

  isStepCurrent(orderStatus: string, stepKey: string): boolean {
    return orderStatus === stepKey;
  }

  trackByOrderId(index: number, order: PortalOrder): number {
    return order.id;
  }

  trackByApprovalId(index: number, approval: PortalApproval): number | string {
    return approval.id;
  }

  trackByStageId(index: number, stage: { id: number | string }): number | string {
    return stage.id;
  }

  trackByContactId(index: number, contact: PortalContact): number {
    return contact.id;
  }

  trackByStatusStep(index: number, step: StatusStep): string {
    return step.key;
  }

  isLoading(action: Exclude<LoadingAction, null>): boolean {
    return this.loadingAction === action;
  }

  isContactTypeAllowed(type: ContactType): boolean {
    return type === 'phone' ? this.allowPhone || Boolean(this.customer) : this.allowEmail || Boolean(this.customer);
  }

  private loadSettings(): void {
    this.loadingAction = 'settings';
    this.portalService.settings()
      .pipe(finalize(() => (this.loadingAction = null)))
      .subscribe({
        next: (settings) => {
          this.settings = settings;
          this.applyBranding(settings);
        },
        error: () => {
          this.settings = {
            brand: { name: 'Repair CRM', accent_color: '#0f766e' },
            auth: {
              policy: 'phone_or_email',
              allow_phone: true,
              allow_email: true,
              require_verified_contact_for_orders: true
            },
            marketing: { promotions: [], banner: null },
            features: {}
          };
        }
      });
  }

  private applyBranding(settings: PortalSettings): void {
    document.documentElement.style.setProperty('--primary', settings.brand.accent_color);
    document.documentElement.style.setProperty('--primary-strong', settings.brand.accent_color);
  }

  private patchProfileForm(customer: PortalCustomer | null): void {
    if (!customer) {
      this.profileForm.reset({ first_name: '', last_name: '', middle_name: '', marketing_consent: false });
      return;
    }

    this.profileForm.patchValue({
      first_name: customer.first_name,
      last_name: customer.last_name,
      middle_name: customer.middle_name || '',
      marketing_consent: customer.marketing_consent
    });
  }

  private contactPayload(value: string): { phone?: string; email?: string } {
    return value.includes('@') ? { email: value } : { phone: value };
  }

  private handleContactChallenge(response: ChallengeResponse): void {
    this.success = response.message;
    this.contactDebugCode = response.debug_code || '';
  }

  private resetOrderForm(): void {
    this.orderForm.reset({
      device_type: 'Телефон',
      brand: '',
      model_name: '',
      serial_number: '',
      imei: '',
      color: '',
      storage_capacity: '',
      accessories: '',
      device_condition: '',
      problem_description: '',
      cost_estimate: 0
    });
  }

  private clearMessages(): void {
    this.error = '';
    this.success = '';
  }

  private extractError(error: unknown): string {
    if (!(error instanceof Object)) {
      return 'Не удалось выполнить действие';
    }
    // HttpErrorResponse wraps the parsed body in `.error`
    const body = (error as { error?: unknown }).error;

    // FastAPI returns { error: string, details: ... }
    if (typeof body === 'string') {
      return body;
    }
    if (body && typeof body === 'object') {
      const b = body as { error?: string; detail?: string; details?: { fields?: string[] } };
      const message = b.error || b.detail || 'Не удалось выполнить действие';
      const fields = b.details?.fields;
      return fields?.length ? `${message}: ${fields.join(', ')}` : message;
    }
    return 'Не удалось выполнить действие';
  }
}
