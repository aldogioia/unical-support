import { Component, signal } from '@angular/core';
import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { DetailPanelDirective } from './detail-panel.directive';

@Component({
  standalone: true,
  imports: [DetailPanelDirective],
  template: `<div class="master-detail">
    <div class="master-pane">
      <button id="panel-opener" (click)="open.set(true)">Apri</button>
    </div>
    @if (open()) {
      <section
        appDetailPanel
        detailLabel="Dettaglio di prova"
        (detailClose)="open.set(false)"
      >
        <button data-panel-close (click)="open.set(false)">Chiudi</button
        ><input aria-label="Nome" /><button id="panel-last">Salva</button>
      </section>
    }
  </div>`,
})
class DetailHost {
  readonly open = signal(false);
}

describe('Responsive detail panel keyboard behavior', () => {
  let mobile: boolean;
  beforeEach(async () => {
    mobile = true;
    spyOn(window, 'matchMedia').and.callFake(
      () =>
        ({
          get matches() {
            return mobile;
          },
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as any,
    );
    await TestBed.configureTestingModule({
      imports: [DetailHost],
    }).compileComponents();
  });
  it('makes the master inert on mobile, traps Tab and restores focus after Escape', fakeAsync(() => {
    const fixture = TestBed.createComponent(DetailHost);
    fixture.detectChanges();
    const opener = fixture.nativeElement.querySelector(
      '#panel-opener',
    ) as HTMLButtonElement;
    opener.focus();
    opener.click();
    fixture.detectChanges();
    tick(17);
    const panel = fixture.nativeElement.querySelector('section') as HTMLElement;
    const close = panel.querySelector('button')!,
      last = panel.querySelector('#panel-last') as HTMLButtonElement;
    expect(panel.getAttribute('role')).toBe('dialog');
    expect(panel.getAttribute('aria-modal')).toBe('true');
    expect(
      fixture.nativeElement.querySelector('.master-pane').inert,
    ).toBeTrue();
    last.focus();
    last.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Tab',
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(document.activeElement).toBe(close);
    close.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('section')).toBeNull();
    expect(
      fixture.nativeElement.querySelector('.master-pane').inert,
    ).toBeFalse();
    expect(document.activeElement).toBe(opener);
    fixture.destroy();
  }));
  it('keeps the list interactive next to the detail on desktop', fakeAsync(() => {
    mobile = false;
    const fixture = TestBed.createComponent(DetailHost);
    fixture.detectChanges();
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    tick(17);
    expect(
      fixture.nativeElement.querySelector('section').getAttribute('role'),
    ).toBe('region');
    expect(
      fixture.nativeElement.querySelector('.master-pane').inert,
    ).toBeFalse();
    fixture.destroy();
  }));
});
