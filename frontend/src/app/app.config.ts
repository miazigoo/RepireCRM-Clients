import { registerLocaleData } from '@angular/common';
import localeRu from '@angular/common/locales/ru';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, DEFAULT_CURRENCY_CODE, LOCALE_ID } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { portalAuthInterceptor } from './portal-auth.interceptor';

registerLocaleData(localeRu);

export const appConfig: ApplicationConfig = {
  providers: [
    { provide: LOCALE_ID, useValue: 'ru-RU' },
    { provide: DEFAULT_CURRENCY_CODE, useValue: 'RUB' },
    provideRouter(routes),
    provideHttpClient(withInterceptors([portalAuthInterceptor])),
    provideAnimationsAsync()
  ]
};
