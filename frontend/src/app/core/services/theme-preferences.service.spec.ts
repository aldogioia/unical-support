import { TestBed } from '@angular/core/testing';
import {
  DEFAULT_THEME,
  THEME_STORAGE_KEY,
  ThemePreferencesService,
} from './theme-preferences.service';

describe('ThemePreferencesService', () => {
  let previous: string | null;
  let attributes: Record<string, string | null>;
  const names = [
    'data-contrast',
    'data-density',
    'data-reading',
    'data-motion',
    'data-theme',
  ];
  beforeEach(() => {
    previous = localStorage.getItem(THEME_STORAGE_KEY);
    attributes = Object.fromEntries(
      names.map((name) => [name, document.documentElement.getAttribute(name)]),
    );
    localStorage.removeItem(THEME_STORAGE_KEY);
    TestBed.configureTestingModule({});
  });
  afterEach(() => {
    TestBed.resetTestingModule();
    if (previous === null) localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, previous);
    names.forEach((name) =>
      attributes[name] === null
        ? document.documentElement.removeAttribute(name)
        : document.documentElement.setAttribute(name, attributes[name]!),
    );
  });
  it('applies persisted preferences before rendering and retains all supported settings', () => {
    const preferences = {
      contrast: 'high',
      density: 'comfortable',
      reading: 'large',
      motion: 'reduced',
    };
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(preferences));
    const service = TestBed.inject(ThemePreferencesService);
    expect(service.preferences()).toEqual(preferences as any);
    expect(document.documentElement.dataset['contrast']).toBe('high');
    expect(document.documentElement.dataset['reading']).toBe('large');
  });
  it('updates the document and persists preferences without making an API call', () => {
    const service = TestBed.inject(ThemePreferencesService);
    service.update({ contrast: 'high', motion: 'reduced' });
    TestBed.flushEffects();
    expect(document.documentElement.dataset['contrast']).toBe('high');
    expect(document.documentElement.dataset['motion']).toBe('reduced');
    expect(JSON.parse(localStorage.getItem(THEME_STORAGE_KEY)!)).toEqual({
      ...DEFAULT_THEME,
      contrast: 'high',
      motion: 'reduced',
    });
  });
  it('recovers from corrupt stored JSON and ignores unknown preference values', () => {
    localStorage.setItem(THEME_STORAGE_KEY, '{invalid');
    expect(TestBed.inject(ThemePreferencesService).preferences()).toEqual(
      DEFAULT_THEME,
    );
    TestBed.resetTestingModule();
    localStorage.setItem(
      THEME_STORAGE_KEY,
      JSON.stringify({
        contrast: 'unexpected',
        density: 'roomy',
        motion: 'forever',
        reading: 'large',
        theme: 'anything',
      }),
    );
    expect(TestBed.inject(ThemePreferencesService).preferences()).toEqual({
      ...DEFAULT_THEME,
      reading: 'large',
    });
  });
  it('continues to apply appearance if browser storage cannot be written', () => {
    const service = TestBed.inject(ThemePreferencesService);
    const storage = spyOn(Storage.prototype, 'setItem').and.throwError(
      'Storage unavailable',
    );
    service.update({ density: 'comfortable' });
    expect(() => TestBed.flushEffects()).not.toThrow();
    expect(document.documentElement.dataset['density']).toBe('comfortable');
    storage.and.callThrough();
  });
  it('restores the defaults for all preferences', () => {
    const service = TestBed.inject(ThemePreferencesService);
    service.update({
      contrast: 'high',
      density: 'comfortable',
      reading: 'large',
      motion: 'reduced',
    });
    service.reset();
    TestBed.flushEffects();
    expect(service.preferences()).toEqual(DEFAULT_THEME);
    expect(document.documentElement.dataset['contrast']).toBe('standard');
  });
});
