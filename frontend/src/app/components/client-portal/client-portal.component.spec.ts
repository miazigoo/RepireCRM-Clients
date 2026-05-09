import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ClientPortalComponent } from './client-portal.component';

describe('ClientPortalComponent', () => {
  let component: ClientPortalComponent;
  let fixture: ComponentFixture<ClientPortalComponent>;

  beforeEach(async () => {
    localStorage.clear();

    await TestBed.configureTestingModule({
      imports: [ClientPortalComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations()
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ClientPortalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('creates the standalone client portal', () => {
    expect(component).toBeTruthy();
  });

  it('starts with anonymous access and quick tracking available', () => {
    expect(component.customer).toBeNull();
    expect(component.trackForm.enabled).toBeTrue();
    expect(component.activeOrdersCount).toBe(0);
  });
});
