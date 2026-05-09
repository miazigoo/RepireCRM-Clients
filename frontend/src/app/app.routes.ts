import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./components/client-portal/client-portal.component').then(
        (module) => module.ClientPortalComponent
      )
  },
  {
    path: '**',
    redirectTo: ''
  }
];
