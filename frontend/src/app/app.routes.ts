import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./components/portal-landing/portal-landing.component').then(
        (m) => m.PortalLandingComponent
      )
  },
  {
    path: 'login',
    loadComponent: () =>
      import('./components/client-portal/client-portal.component').then((m) => m.ClientPortalComponent)
  },
  {
    path: '**',
    redirectTo: ''
  }
];
