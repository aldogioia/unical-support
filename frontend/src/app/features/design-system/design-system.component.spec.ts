import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { DesignSystemComponent } from './design-system.component';
import { DsPlaygroundComponent } from './ds-playground.component';

describe('DesignSystemComponent accessibility preview', () => {
  let fixture: ComponentFixture<DesignSystemComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [DesignSystemComponent] }).compileComponents();
    fixture = TestBed.createComponent(DesignSystemComponent);
    fixture.detectChanges();
  });

  afterEach(() => fixture.destroy());

  it('applies contrast only to its host when the native switch is clicked', () => {
    const rootBorder = getComputedStyle(document.documentElement).getPropertyValue('--ds-border');
    fixture.componentInstance.openPreferences();
    const toggle = fixture.nativeElement.querySelector('.preferences input') as HTMLInputElement;
    toggle.click();
    fixture.detectChanges();
    expect(toggle.checked).toBeTrue();
    expect(fixture.nativeElement.classList.contains('ds-high-contrast')).toBeTrue();
    expect(getComputedStyle(fixture.nativeElement).getPropertyValue('--ds-stroke').trim()).toBe('2px');
    expect(getComputedStyle(document.documentElement).getPropertyValue('--ds-border')).toBe(rootBorder);
    expect(fixture.nativeElement.querySelector('.preferences').open).toBeTrue();
    fixture.componentInstance.closePreferences();
  });

  it('restores all appearance preferences without changing global styles', () => {
    const component = fixture.componentInstance;
    component.highContrast.set(true);
    component.comfortable.set(true);
    component.reduceMotion.set(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.classList.contains('ds-reduce-motion')).toBeTrue();
    const skeleton = fixture.nativeElement.querySelector('.skeleton');
    expect(getComputedStyle(skeleton).animationName).toBe('none');
    component.resetPreferences();
    fixture.detectChanges();
    expect(fixture.nativeElement.className).not.toContain('ds-high-contrast');
    expect(fixture.nativeElement.className).not.toContain('ds-comfortable');
    expect(fixture.nativeElement.className).not.toContain('ds-reduce-motion');
  });

  it('filters navigation and recovers after an empty search', () => {
    fixture.componentInstance.search.set('inesistente');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('nav').textContent).toContain('Nessuna sezione');
    fixture.componentInstance.search.set('email');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('nav a').length).toBe(1);
    fixture.componentInstance.search.set('');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('nav a').length).toBe(5);
  });
});

describe('DsPlaygroundComponent interactions', () => {
  let fixture: ComponentFixture<DsPlaygroundComponent>;
  let component: DsPlaygroundComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [DsPlaygroundComponent] }).compileComponents();
    fixture = TestBed.createComponent(DsPlaygroundComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => fixture.destroy());

  it('validates edited addresses and connects the error to the input', () => {
    const email = fixture.nativeElement.querySelector('#ds-email') as HTMLInputElement;
    expect(email.getAttribute('aria-invalid')).toBe('true');
    email.value = 'student@example.org';
    email.dispatchEvent(new Event('input', { bubbles: true }));
    fixture.detectChanges();
    expect(email.getAttribute('aria-invalid')).toBe('false');
    expect(fixture.nativeElement.querySelector('#ds-email-hint').textContent).toContain('valido');
  });

  it('initially selects the provider shown in the helper text', () => {
    const select = fixture.nativeElement.querySelector('#ds-provider') as HTMLSelectElement;
    expect(select.value).toBe('Google');
    select.value = 'OpenAI';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
    expect(component.provider()).toBe('OpenAI');
  });

  it('disables sending while busy and dismisses its completion toast', fakeAsync(() => {
    const button = fixture.nativeElement.querySelector('.live-action button') as HTMLButtonElement;
    button.click(); fixture.detectChanges();
    expect(button.disabled).toBeTrue();
    expect(button.getAttribute('aria-busy')).toBe('true');
    tick(1600); fixture.detectChanges();
    expect(button.disabled).toBeFalse();
    expect(fixture.nativeElement.querySelector('.toast').textContent).toContain('Email inviata');
    tick(4500); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.toast')).toBeNull();
  }));

  it('keeps draft edits and updates the character counter', () => {
    const editor = fixture.nativeElement.querySelector('#ds-draft') as HTMLTextAreaElement;
    editor.value = 'Risposta revisionata.';
    editor.dispatchEvent(new Event('input', { bubbles: true }));
    fixture.detectChanges();
    expect(component.draft()).toBe('Risposta revisionata.');
    expect(fixture.nativeElement.querySelector('.editor-footer').textContent).toContain('21 caratteri');
  });

  it('makes the editor read-only until regeneration completes', fakeAsync(() => {
    component.regenerate(); fixture.detectChanges();
    const editor = fixture.nativeElement.querySelector('#ds-draft') as HTMLTextAreaElement;
    expect(editor.readOnly).toBeTrue();
    tick(1300); fixture.detectChanges();
    expect(editor.readOnly).toBeFalse();
    expect(editor.value).toContain('fototessera');
    fixture.destroy();
    tick(5000);
  }));

  it('filters emails with keyboard tabs and maintains a single tab stop', () => {
    const tabs = fixture.nativeElement.querySelectorAll('[role="tab"]') as NodeListOf<HTMLButtonElement>;
    tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    fixture.detectChanges();
    expect(tabs[2].getAttribute('aria-selected')).toBe('true');
    expect(tabs[2].tabIndex).toBe(0);
    expect(tabs[0].tabIndex).toBe(-1);
    expect(fixture.nativeElement.querySelectorAll('.email-item').length).toBe(1);
    expect(fixture.nativeElement.querySelector('.email-item').textContent).toContain('Sara Ferraro');
  });

  it('validates local files, rejects unsupported files and never uploads', () => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['demo'], 'guida.pdf', { type: 'application/pdf' }));
    transfer.items.add(new File(['demo'], 'script.exe'));
    const input = fixture.nativeElement.querySelector('input[type=file]') as HTMLInputElement;
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
    expect(component.files()).toEqual(['guida.pdf']);
    expect(fixture.nativeElement.querySelector('#ds-file-error').textContent).toContain('non sono validi');
    component.removeFile('guida.pdf'); fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.file-list>div').length).toBe(0);
  });

  it('cancels pending simulation timers when leaving the page', fakeAsync(() => {
    component.simulateSend(); component.regenerate();
    fixture.destroy(); tick(10000);
    expect(component.toast()).toBeNull();
  }));
});
