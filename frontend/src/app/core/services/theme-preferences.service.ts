import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';

export interface ThemePreferences {
  contrast: 'standard' | 'high';
  density: 'compact' | 'comfortable';
  reading: 'normal' | 'large';
  motion: 'full' | 'reduced';
}

export const THEME_STORAGE_KEY = 'unical-support.theme.v1';
export const DEFAULT_THEME: ThemePreferences = {
  contrast: 'standard',
  density: 'compact',
  reading: 'normal',
  motion: 'full',
};

@Injectable({ providedIn: 'root' })
export class ThemePreferencesService {
  private readonly document = inject(DOCUMENT);
  private readonly state = signal<ThemePreferences>(this.read());
  readonly preferences = this.state.asReadonly();
  readonly highContrast = computed(() => this.state().contrast === 'high');

  constructor() {
    this.apply(this.state());
    effect(() => {
      const preferences = this.state();
      this.apply(preferences);
      try {
        this.document.defaultView?.localStorage.setItem(
          THEME_STORAGE_KEY,
          JSON.stringify(preferences),
        );
      } catch {
        /* Storage can be unavailable in private sessions. */
      }
    });
  }

  update(preferences: Partial<ThemePreferences>): void {
    this.state.update((current) => ({ ...current, ...preferences }));
  }
  reset(): void {
    this.state.set({ ...DEFAULT_THEME });
  }

  private read(): ThemePreferences {
    try {
      const stored = JSON.parse(
        this.document.defaultView?.localStorage.getItem(THEME_STORAGE_KEY) ||
          'null',
      );
      return {
        contrast: stored?.contrast === 'high' ? 'high' : DEFAULT_THEME.contrast,
        density:
          stored?.density === 'comfortable'
            ? 'comfortable'
            : DEFAULT_THEME.density,
        reading: stored?.reading === 'large' ? 'large' : DEFAULT_THEME.reading,
        motion: stored?.motion === 'reduced' ? 'reduced' : DEFAULT_THEME.motion,
      };
    } catch {
      return { ...DEFAULT_THEME };
    }
  }

  private apply(preferences: ThemePreferences): void {
    const root = this.document.documentElement;
    root.dataset['contrast'] = preferences.contrast;
    root.dataset['density'] = preferences.density;
    root.dataset['reading'] = preferences.reading;
    root.dataset['motion'] = preferences.motion;
    root.dataset['theme'] = 'light'; // Explicit theme attribute also provides the hook for a future dark palette.
  }
}
