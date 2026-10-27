import { emailPage } from './review-test-data';
import { ComponentFixture, TestBed, fakeAsync, flushMicrotasks, tick } from '@angular/core/testing';
import { Api } from '../../../../core/api/api';
import { fetchEmailsNowApiEmailsFetchNowPost } from '../../../../core/api/fn/emails/fetch-emails-now-api-emails-fetch-now-post';
import { readEmailFetchStatusApiEmailsFetchStatusJobIdGet } from '../../../../core/api/fn/emails/read-email-fetch-status-api-emails-fetch-status-job-id-get';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../../../../core/api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
import { ReviewDashboardComponent } from './review-dashboard.component';

describe('ReviewDashboardComponent manual fetch', () => {
  let fixture: ComponentFixture<ReviewDashboardComponent>;
  let component: ReviewDashboardComponent;
  let api: jasmine.SpyObj<Api>;
  const job = {job_id: '00000000-0000-0000-0000-000000000001', status: 'queued', message: 'In coda', fetched_count: 0};

  beforeEach(async () => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    await TestBed.configureTestingModule({imports: [ReviewDashboardComponent], providers: [{provide: Api, useValue: api}]}).compileComponents();
    fixture = TestBed.createComponent(ReviewDashboardComponent);
    component = fixture.componentInstance;
  });

  it('disables the button until polling finishes and shows the final result', fakeAsync(() => {
    let checks = 0;
    api.invoke.and.callFake(((operation: unknown) => {
      if (operation === fetchEmailsNowApiEmailsFetchNowPost) return Promise.resolve(job);
      if (operation === readEmailFetchStatusApiEmailsFetchStatusJobIdGet) return Promise.resolve(++checks === 1 ? job : {...job, status: 'completed', message: 'Controllo completato: 2 nuove email.', fetched_count: 2});
      return Promise.resolve(emailPage([]));
    }) as any);
    fixture.detectChanges(); flushMicrotasks();
    component.fetchEmails(); flushMicrotasks(); tick(0); flushMicrotasks(); fixture.detectChanges();
    expect(component.fetching()).toBeTrue();
    expect(fixture.nativeElement.querySelector('button[aria-busy]').disabled).toBeTrue();
    component.fetchEmails(); flushMicrotasks();
    expect(api.invoke.calls.allArgs().filter(args => args[0] === fetchEmailsNowApiEmailsFetchNowPost).length).toBe(1);
    tick(1500); flushMicrotasks(); fixture.detectChanges();
    expect(component.fetching()).toBeFalse();
    expect(fixture.nativeElement.querySelector('[role="status"]').textContent).toContain('2 nuove email');
    fixture.destroy();
  }));

  it('shows a Gmail error and enables retry', fakeAsync(() => {
    api.invoke.and.callFake(((operation: unknown) => {
      if (operation === fetchEmailsNowApiEmailsFetchNowPost) return Promise.resolve(job);
      if (operation === readEmailFetchStatusApiEmailsFetchStatusJobIdGet) return Promise.resolve({...job, status: 'failed', message: 'Verifica le credenziali OAuth.'});
      return Promise.resolve(emailPage([]));
    }) as any);
    fixture.detectChanges(); flushMicrotasks();
    component.fetchEmails(); flushMicrotasks(); tick(0); flushMicrotasks();
    expect(component.fetching()).toBeFalse();
    expect(component.toast()?.error).toBeTrue();
    expect(component.toast()?.message).toContain('OAuth');
    fixture.destroy();
  }));

  it('stops following a request if the page is destroyed while enqueueing', fakeAsync(() => {
    let finish!: (job: any) => void;
    api.invoke.and.callFake(((operation: unknown) => operation === fetchEmailsNowApiEmailsFetchNowPost ? new Promise(resolve => finish = resolve) : Promise.resolve(emailPage([]))) as any);
    fixture.detectChanges(); flushMicrotasks();
    component.fetchEmails(); fixture.destroy();
    finish(job); flushMicrotasks(); tick(2000);
    expect(api.invoke.calls.allArgs().filter(args => args[0] === readEmailFetchStatusApiEmailsFetchStatusJobIdGet).length).toBe(0);
  }));

  it('keeps the draft visible when Gmail sending fails', fakeAsync(() => {
    const email: any = {id: 'email-1', status: 'DRAFT', sender: 'student@example.org', body: 'Domanda'};
    api.invoke.and.callFake(((operation: unknown) => operation === updateEmailDraftApiEmailsEmailIdDraftPut ? Promise.resolve({...email, status: 'FAILED'}) : Promise.resolve(emailPage([email]))) as any);
    fixture.detectChanges(); flushMicrotasks();
    component.handleApprove({email, draft: 'Risposta'}); flushMicrotasks();
    expect(component.emails().length).toBe(1);
    expect(component.emails()[0].status).toBe('FAILED');
    expect(component.toast()?.error).toBeTrue();
    fixture.destroy();
  }));
});
