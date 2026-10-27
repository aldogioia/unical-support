import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { LoadMoreDirective } from './load-more.directive';

@Component({ standalone: true, imports: [LoadMoreDirective], template: '<div class="master-pane"><div appLoadMore [enabled]="enabled()" (loadMore)="requests = requests + 1"></div></div>' })
class InfiniteList { enabled = signal(true); requests = 0; }

describe('Infinite scroll trigger', () => {
  it('observes within the list scroll container and disconnects when unavailable', () => {
    let callback!: IntersectionObserverCallback;
    let observedRoot: Element | Document | null | undefined;
    const disconnect = jasmine.createSpy('disconnect');
    spyOn(window, 'IntersectionObserver').and.callFake(function (handler, options) {
      callback = handler; observedRoot = options?.root;
      return { observe: () => {}, unobserve: () => {}, disconnect, takeRecords: () => [], root: options?.root, rootMargin: '320px', thresholds: [] } as unknown as IntersectionObserver;
    });
    const fixture = TestBed.createComponent(InfiniteList); fixture.detectChanges();
    expect(observedRoot).toBe(fixture.nativeElement.querySelector('.master-pane'));
    callback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    expect(fixture.componentInstance.requests).toBe(1);
    fixture.componentInstance.enabled.set(false); fixture.detectChanges();
    expect(disconnect).toHaveBeenCalled();
    fixture.destroy();
  });
});
