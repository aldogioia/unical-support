import { TestBed, fakeAsync, flushMicrotasks, tick } from '@angular/core/testing';
import { Api } from '../../../core/api/api';
import { previewEmailDraftApiEmailsEmailIdPreviewPost } from '../../../core/api/fn/emails/preview-email-draft-api-emails-email-id-preview-post';
import { EmailPreviewComponent } from './email-preview.component';

describe('Official email preview', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(() => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    TestBed.configureTestingModule({ imports: [EmailPreviewComponent], providers: [{ provide: Api, useValue: api }] });
  });
  function create(draft = 'Risposta modificata') {
    const fixture = TestBed.createComponent(EmailPreviewComponent);
    fixture.componentRef.setInput('emailId', 'email-1');
    fixture.componentRef.setInput('draft', draft);
    fixture.detectChanges();
    return fixture;
  }

  it('previews unsaved text using only the preview endpoint and isolates the HTML', fakeAsync(() => {
    api.invoke.and.returnValue(Promise.resolve({ html: '<p>Anteprima ufficiale</p>' }) as any);
    const fixture = create();
    tick(300); flushMicrotasks(); fixture.detectChanges();
    expect(api.invoke).toHaveBeenCalledOnceWith(previewEmailDraftApiEmailsEmailIdPreviewPost, { email_id: 'email-1', body: { generated_draft: 'Risposta modificata' } });
    const frame = fixture.nativeElement.querySelector('iframe');
    expect(frame.getAttribute('sandbox')).toBe('allow-same-origin');
    expect(frame.getAttribute('sandbox')).not.toContain('allow-scripts');
    expect(frame.getAttribute('srcdoc')).toContain('Content-Security-Policy');
    expect(frame.getAttribute('scrolling')).toBe('no');
    expect(frame.getAttribute('srcdoc')).toContain('Anteprima ufficiale');
    fixture.destroy();
  }));

  it('fits the rendered document height and follows body reflow without a fixed viewport cap', fakeAsync(() => {
    const fixture = create();
    const body = document.createElement('div');
    let bodyHeight = 1200;
    spyOn(body, 'getBoundingClientRect').and.callFake(() => ({ height: bodyHeight } as DOMRect));
    Object.defineProperty(body, 'scrollHeight', { get: () => bodyHeight });
    let reflow!: ResizeObserverCallback;
    const disconnect = jasmine.createSpy('disconnect');
    spyOn(window, 'ResizeObserver').and.callFake(function (callback: ResizeObserverCallback) {
      reflow = callback;
      return { observe: () => {}, disconnect, unobserve: () => {} } as unknown as ResizeObserver;
    });
    const frame = { contentDocument: { body }, style: { height: '' }, offsetHeight: 2, clientHeight: 0 };
    fixture.componentInstance.fitPreview({ target: frame } as unknown as Event);
    expect(frame.style.height).toBe('1202px');
    bodyHeight = 500;
    reflow([], {} as ResizeObserver);
    expect(frame.style.height).toBe('502px');
    fixture.destroy();
    expect(disconnect).toHaveBeenCalled();
    tick(300);
    expect(api.invoke).not.toHaveBeenCalled();
  }));

  it('debounces edits and ignores a stale response after switching email', fakeAsync(() => {
    let finishOld!: (result: any) => void;
    api.invoke.and.returnValue(new Promise(resolve => finishOld = resolve) as any);
    const fixture = create();
    tick(300);
    fixture.componentRef.setInput('emailId', 'email-2');
    fixture.componentRef.setInput('draft', 'Seconda bozza');
    fixture.detectChanges();
    api.invoke.and.returnValue(Promise.resolve({ html: '<p>Seconda bozza</p>' }) as any);
    tick(300); flushMicrotasks();
    finishOld({ html: '<p>Obsoleta</p>' }); flushMicrotasks(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('iframe').getAttribute('srcdoc')).toContain('Seconda bozza');
    expect(fixture.nativeElement.querySelector('iframe').getAttribute('srcdoc')).not.toContain('Obsoleta');
    fixture.destroy();
  }));

  it('does not request an empty draft and reports a failed preview without rendering stale HTML', fakeAsync(() => {
    const fixture = create('  ');
    tick(300); fixture.detectChanges();
    expect(api.invoke).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('Scrivi una risposta');
    api.invoke.and.callFake(() => Promise.reject({ status: 503 }));
    fixture.componentRef.setInput('draft', 'Bozza'); fixture.detectChanges();
    tick(300); flushMicrotasks(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('non disponibile');
    expect(fixture.nativeElement.querySelector('iframe')).toBeNull();
    fixture.destroy();
  }));
});
