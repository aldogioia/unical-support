import { DestroyRef, Injectable, inject, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ShellUiService {
  private readonly media = window.matchMedia('(max-width:1023px)');
  readonly narrow = signal(this.media.matches);
  constructor() {
    const update = () => {
      this.narrow.set(this.media.matches);
      if (!this.media.matches) this.mobileOpen.set(false);
    };
    this.media.addEventListener('change', update);
    inject(DestroyRef).onDestroy(() =>
      this.media.removeEventListener('change', update),
    );
  }
  readonly collapsed = signal(false);
  readonly mobileOpen = signal(false);
  readonly emailFilters = [
    { value: 'DRAFT', label: 'Bozze' },
    { value: 'ESCALATED', label: 'Da gestire' },
    { value: 'TO_RESPOND', label: 'In elaborazione' },
    { value: 'FAILED', label: 'Errori' },
    { value: 'SENT', label: 'Inviate' },
  ];
  readonly emailStatus = signal('ALL');
  readonly emailMenuExpanded = signal(true);
  readonly emailCounts = signal<Partial<Record<string, number>>>({});
  readonly detailFooterHeight = signal(0);
  readonly emailCount = signal<{ count: number; label: string } | null>(null);
  toggleNavigation(): void {
    if (this.narrow()) this.mobileOpen.update((value) => !value);
    else this.collapsed.update((value) => !value);
  }
  closeNavigation(): void {
    this.mobileOpen.set(false);
  }
}
