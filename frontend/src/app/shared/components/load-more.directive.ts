import { Directive, ElementRef, effect, inject, input, output } from '@angular/core';

@Directive({ selector: '[appLoadMore]', standalone: true })
export class LoadMoreDirective {
  readonly enabled = input(false);
  readonly loadMore = output<void>();
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  constructor() {
    effect(onCleanup => {
      if (!this.enabled()) return;
      const target = this.element.nativeElement;
      const observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) this.loadMore.emit();
      }, { root: target.closest('.master-pane'), rootMargin: '320px 0px' });
      observer.observe(target);
      onCleanup(() => observer.disconnect());
    });
  }
}
