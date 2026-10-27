import { TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { Api } from '../../../../core/api/api';
import { EmailResponse } from '../../../../core/api/models/email-response';
import { readEmailPageApiEmailsPageGet } from '../../../../core/api/fn/emails/read-email-page-api-emails-page-get';
import { readEmailApiEmailsEmailIdGet } from '../../../../core/api/fn/emails/read-email-api-emails-email-id-get';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../../../../core/api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
import { retryFailedEmailApiEmailsEmailIdRetryPost } from '../../../../core/api/fn/emails/retry-failed-email-api-emails-email-id-retry-post';
import { retryFailedEmailBatchApiEmailsRetryFailedPost } from '../../../../core/api/fn/emails/retry-failed-email-batch-api-emails-retry-failed-post';
import { ReviewDashboardComponent } from './review-dashboard.component';
import { emailPage } from './review-test-data';

const entry: EmailResponse = { id: 'email-1', gmail_id: 'gmail-1', sender: 'student@example.org', status: 'DRAFT', subject: 'Test', generated_draft: 'Bozza iniziale', draft_revision: 0, received_at: '2026-10-26T00:30:00Z', categories: [] };

describe('Review pagination and draft ownership', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(() => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.returnValue(Promise.resolve(emailPage([entry])) as any);
    TestBed.configureTestingModule({ imports: [ReviewDashboardComponent], providers: [{ provide: Api, useValue: api }] });
  });
  function create() {
    const fixture = TestBed.createComponent(ReviewDashboardComponent);
    fixture.detectChanges(); flushMicrotasks();
    return fixture;
  }

  it('groups dates in Europe/Rome and gives headers sticky positioning', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    page.emails.set([entry, { ...entry, id: 'email-2', received_at: '2026-10-25T23:30:00Z' }, { ...entry, id: 'email-3', received_at: '2026-10-25T00:00:00Z' }]);
    fixture.detectChanges();
    expect(page.groupedEmails().map(group => [group.key, group.emails.length])).toEqual([['2026-10-26', 2], ['2026-10-25', 1]]);
    expect(getComputedStyle(fixture.nativeElement.querySelector('.email-date-heading')).position).toBe('sticky');
    fixture.destroy();
  }));

  it('loads the next cursor once and deduplicates a repeated item', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    let complete!: (value: any) => void;
    api.invoke.and.returnValue(new Promise(resolve => complete = resolve) as any);
    page.nextCursor.set('cursor-1');
    const before = api.invoke.calls.count();
    page.loadMore(); page.loadMore();
    expect(api.invoke.calls.count()).toBe(before + 1);
    expect(api.invoke).toHaveBeenCalledWith(readEmailPageApiEmailsPageGet, { cursor: 'cursor-1', limit: 50 });
    complete(emailPage([entry, { ...entry, id: 'email-2' }], null, 2)); flushMicrotasks();
    expect(page.emails().length).toBe(2);
    expect(page.nextCursor()).toBeNull();
    fixture.destroy();
  }));

  it('automatically requests another page when the real list scroll reaches its sentinel', async () => {
    const items = Array.from({ length: 50 }, (_, index) => ({ ...entry, id: `scroll-${index}`, subject: `Email ${index}` }));
    let pageCalls = 0;
    api.invoke.and.callFake(((operation: unknown) => Promise.resolve(operation === readEmailPageApiEmailsPageGet && ++pageCalls === 1
      ? emailPage(items, 'scroll-cursor', 51)
      : emailPage([{ ...entry, id: 'scroll-last' }], null, 51))) as any);
    const fixture = TestBed.createComponent(ReviewDashboardComponent);
    fixture.nativeElement.style.cssText = 'display:block;height:360px;width:900px';
    try {
      fixture.detectChanges();
      await new Promise(resolve => setTimeout(resolve, 0)); fixture.detectChanges();
      const list = fixture.nativeElement.querySelector('.master-pane') as HTMLElement;
      expect(list.scrollHeight).toBeGreaterThan(list.clientHeight);
      list.scrollTop = list.scrollHeight;
      list.dispatchEvent(new Event('scroll'));
      for (let attempt = 0; attempt < 40 && pageCalls < 2; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 20)); fixture.detectChanges();
      }
      expect(api.invoke).toHaveBeenCalledWith(readEmailPageApiEmailsPageGet, { cursor: 'scroll-cursor', limit: 50 });
      expect(fixture.componentInstance.emails().length).toBe(51);
      expect(fixture.componentInstance.nextCursor()).toBeNull();
    } finally { fixture.destroy(); }
  });

  it('ignores an old page after switching status while it is loading', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    let complete!: (value: any) => void;
    api.invoke.and.returnValue(new Promise(resolve => complete = resolve) as any);
    page.nextCursor.set('old-cursor'); page.loadMore();
    api.invoke.and.returnValue(Promise.resolve(emailPage([])) as any);
    page.setStatus('FAILED'); flushMicrotasks();
    complete(emailPage([{ ...entry, id: 'obsolete' }])); flushMicrotasks();
    expect(page.emails()).toEqual([]);
    expect(page.loadingMore()).toBeFalse();
    fixture.destroy();
  }));

  it('keeps the panel and the exact local text when refresh removes the email from the filtered list', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    page.selectEmail(entry); page.editableDraft.set('Modifiche operatore');
    const remote = { ...entry, status: 'SENT', generated_draft: 'Versione server', draft_revision: 1 };
    api.invoke.and.callFake(((operation: unknown) => Promise.resolve(operation === readEmailApiEmailsEmailIdGet ? remote : emailPage([]))) as any);
    page.loadEmails(false); flushMicrotasks(); fixture.detectChanges();
    expect(page.emails()).toEqual([]);
    expect(page.selectedEmail()?.id).toBe(entry.id);
    expect(fixture.nativeElement.querySelector('.detail-pane')).not.toBeNull();
    expect(page.editableDraft()).toBe('Modifiche operatore');
    expect(page.remoteEmail()?.generated_draft).toBe('Versione server');
    fixture.destroy();
  }));

  it('preserves text on HTTP 409 and lets the operator explicitly keep it on the new revision', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    page.selectEmail(entry); page.editableDraft.set('Testo locale');
    const remote = { ...entry, draft_revision: 1, generated_draft: 'Modifiche altro operatore' };
    api.invoke.and.callFake(((operation: unknown) => operation === updateEmailDraftApiEmailsEmailIdDraftPut ? Promise.reject({ status: 409 }) : Promise.resolve(remote)) as any);
    page.saveDraft(); flushMicrotasks();
    expect(page.editableDraft()).toBe('Testo locale');
    expect(page.remoteEmail()?.draft_revision).toBe(1);
    expect(page.selectedEmail()?.draft_revision).toBe(0);
    page.keepLocalVersion();
    expect(page.editableDraft()).toBe('Testo locale');
    expect(page.selectedEmail()?.draft_revision).toBe(1);
    expect(page.dirty()).toBeTrue();
    fixture.destroy();
  }));

  it('cancels a pending list reload when saving and never leaves the list spinner stuck', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    page.selectEmail(entry); page.editableDraft.set('Testo salvato');
    let finishList!: (value: any) => void;
    api.invoke.and.returnValue(new Promise(resolve => finishList = resolve) as any);
    page.loadEmails();
    expect(page.loading()).toBeTrue();
    api.invoke.and.returnValue(Promise.resolve({ ...entry, generated_draft: 'Testo salvato', draft_revision: 1 }) as any);
    page.saveDraft(); flushMicrotasks();
    finishList(emailPage([])); flushMicrotasks();
    expect(page.loading()).toBeFalse();
    expect(page.selectedEmail()?.draft_revision).toBe(1);
    expect(page.editableDraft()).toBe('Testo salvato');
    expect(page.emails().length).toBe(1);
    fixture.destroy();
  }));

  it('protects unsaved text on page exit and before browser unload', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    page.selectEmail(entry); page.editableDraft.set('Modifiche');
    spyOn(window, 'confirm').and.returnValue(false);
    expect(page.canLeave()).toBeFalse();
    const event = new Event('beforeunload', { cancelable: true });
    page.protectUnsavedDraft(event as BeforeUnloadEvent);
    expect(event.defaultPrevented).toBeTrue();
    fixture.destroy();
  }));

  it('retries a failed processing job only once and preserves the previous text while queued', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    const failed = { ...entry, status: 'FAILED' as const };
    page.emails.set([failed]); page.selectEmail(failed);
    let complete!: (value: any) => void;
    api.invoke.and.returnValue(new Promise(resolve => complete = resolve) as any);
    page.retrySelected(); page.retrySelected();
    expect(api.invoke.calls.allArgs().filter(args => args[0] === retryFailedEmailApiEmailsEmailIdRetryPost).length).toBe(1);
    api.invoke.and.returnValue(Promise.resolve(emailPage([])) as any);
    complete({ ...failed, status: 'TO_CLASSIFY', draft_revision: 1 }); flushMicrotasks();
    expect(page.selectedEmail()?.status).toBe('TO_CLASSIFY');
    expect(page.editableDraft()).toBe('Bozza iniziale');
    fixture.destroy();
  }));

  it('excludes the open email from global retry and never calls the draft/send endpoint', fakeAsync(() => {
    const fixture = create(), page = fixture.componentInstance;
    page.selectEmail(entry);
    api.invoke.and.callFake(((operation: unknown) => Promise.resolve(operation === retryFailedEmailBatchApiEmailsRetryFailedPost ? { queued_count: 2, skipped_count: 1, failed_count: 0 } : emailPage([entry]))) as any);
    page.retryFailed(); flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(retryFailedEmailBatchApiEmailsRetryFailedPost, { body: { exclude_ids: [entry.id] } });
    expect(api.invoke.calls.allArgs().some(args => args[0] === updateEmailDraftApiEmailsEmailIdDraftPut)).toBeFalse();
    fixture.destroy();
  }));
});
