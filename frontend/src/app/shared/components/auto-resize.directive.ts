import { AfterViewChecked, AfterViewInit, DestroyRef, Directive, ElementRef, HostListener, inject } from '@angular/core';

/** Fits initial, programmatically updated and typed text; the surrounding panel owns scrolling. */
@Directive({
  selector: 'textarea[appAutoResize]', standalone: true,
  host: { style: 'overflow-y:hidden;resize:none;max-height:none' },
})
export class AutoResizeDirective implements AfterViewInit, AfterViewChecked {
  private readonly textarea = inject<ElementRef<HTMLTextAreaElement>>(ElementRef).nativeElement;
  private lastValue: string | undefined;
  private lastLayout = '';
  private observer?: ResizeObserver;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.observer?.disconnect());
  }
  ngAfterViewInit(): void {
    this.observer = new ResizeObserver(() => this.checkSize());
    this.observer.observe(this.textarea);
    this.checkSize();
  }
  ngAfterViewChecked(): void { this.checkSize(); }
  @HostListener('input') resizeOnInput(): void { this.checkSize(); }

  private checkSize(): void {
    const field = this.textarea;
    if (!field.getClientRects().length || !field.clientWidth) return;
    const style = getComputedStyle(field);
    const layout = `${field.clientWidth}|${style.font}|${style.lineHeight}|${style.padding}|${style.borderWidth}`;
    if (field.value === this.lastValue && layout === this.lastLayout) return;
    this.lastValue = field.value;
    this.lastLayout = layout;
    const border = style.boxSizing === 'border-box' ? parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth) : 0;
    field.style.height = 'auto';
    field.style.height = `${Math.ceil(field.scrollHeight + border)}px`;
  }
}
