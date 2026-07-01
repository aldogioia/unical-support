import { Injectable, signal, WritableSignal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class SettingsService {

  public darkMode: WritableSignal<boolean> = signal(false);

  constructor() {
    this.initializeSystemTheme();
  }

  private initializeSystemTheme() {
    if (typeof window !== 'undefined' && window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

      this.darkMode.set(mediaQuery.matches);

      mediaQuery.addEventListener('change', (event) => {
        this.darkMode.set(event.matches);
      });
    }
  }
}
