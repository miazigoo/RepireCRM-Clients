import { Component, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AnalyticsService } from './services/analytics.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  private readonly analytics = inject(AnalyticsService);

  constructor() {
    this.analytics.init();
  }

  protected readonly title = signal('repair-crm-client');
}
