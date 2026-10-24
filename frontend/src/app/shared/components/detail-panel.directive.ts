import {
  AfterViewInit,
  ChangeDetectorRef,
  DestroyRef,
  Directive,
  ElementRef,
  HostListener,
  inject,
  input,
  output,
} from '@angular/core';

/** Keyboard/focus behavior for the same detail region on desktop and as a mobile slide-over. */
@Directive({
  selector: '[appDetailPanel]',
  standalone: true,
  host: {
    tabindex: '-1',
    '[attr.role]': 'media.matches ? "dialog" : "region"',
    '[attr.aria-modal]': 'media.matches ? "true" : null',
    '[attr.aria-label]': 'detailLabel()',
  },
})
export class DetailPanelDirective implements AfterViewInit {
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly cdr = inject(ChangeDetectorRef);
  readonly media = window.matchMedia('(max-width:1023px)');
  readonly detailLabel = input('Dettaglio');
  readonly detailClose = output<void>();
  private previousFocus = document.activeElement as HTMLElement | null;
  private master?: HTMLElement | null;
  private frame = 0;
  ngAfterViewInit(): void {
    this.master =
      this.element.nativeElement.parentElement?.querySelector<HTMLElement>(
        '.master-pane',
      );
    const update = () => {
      if (this.master) this.master.inert = this.media.matches;
      this.cdr.markForCheck();
    };
    update();
    this.media.addEventListener('change', update);
    this.frame = requestAnimationFrame(() =>
      this.element.nativeElement
        .querySelector<HTMLElement>('[data-panel-close]')
        ?.focus(),
    );
    this.destroyRef.onDestroy(() => {
      cancelAnimationFrame(this.frame);
      this.media.removeEventListener('change', update);
      if (this.master) this.master.inert = false;
      if (this.previousFocus?.isConnected)
        this.previousFocus.focus({ preventScroll: true });
    });
  }
  @HostListener('keydown', ['$event']) onKey(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.detailClose.emit();
    }
    if (event.key !== 'Tab' || !this.media.matches) return;
    const elements = Array.from(
      this.element.nativeElement.querySelectorAll<HTMLElement>(
        'button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary,[tabindex="0"]',
      ),
    ).filter((e) => e.getClientRects().length > 0);
    const first = elements[0],
      last = elements[elements.length - 1];
    if (!first) {
      event.preventDefault();
      return;
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
