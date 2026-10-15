import { TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { Api } from '../../../../core/api/api';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../../../../core/api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
import { ReviewDashboardComponent } from './review-dashboard.component';
import { EmailResponse } from '../../../../core/api/models/email-response';

const example: EmailResponse = {
  id: 'email-1',
  gmail_id: 'gmail-1',
  sender: 'student@example.org',
  subject: 'Immatricolazione',
  body: 'Vorrei informazioni sul corso',
  status: 'DRAFT',
  generated_draft: 'Risposta iniziale',
  categories: [],
};

describe('Review hub master-detail', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(async () => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.returnValue(Promise.resolve([example]) as any);
    await TestBed.configureTestingModule({
      imports: [ReviewDashboardComponent],
      providers: [{ provide: Api, useValue: api }],
    }).compileComponents();
  });
  it('opens a full detail panel from a row and filters sender, subject and content locally', fakeAsync(() => {
    const fixture = TestBed.createComponent(ReviewDashboardComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.detail-pane')).toBeNull();
    fixture.nativeElement.querySelector('.email-row').click();
    fixture.detectChanges();
    expect(
      fixture.nativeElement
        .querySelector('.master-detail')
        .classList.contains('has-detail'),
    ).toBeTrue();
    expect(fixture.nativeElement.querySelector('#email-draft').value).toBe(
      'Risposta iniziale',
    );
    const calls = api.invoke.calls.count();
    component.search.set('corso');
    expect(component.filteredEmails().length).toBe(1);
    component.search.set('nessuna corrispondenza');
    expect(component.filteredEmails().length).toBe(0);
    expect(api.invoke.calls.count()).toBe(calls);
    component.closeDetail();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.detail-pane')).toBeNull();
    fixture.destroy();
  }));
  it('preserves edited text during background refresh and repeated selection', fakeAsync(() => {
    const fixture = TestBed.createComponent(ReviewDashboardComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectEmail(example);
    component.editableDraft.set('Testo revisionato');
    component.selectEmail(example);
    component.loadEmails(false);
    flushMicrotasks();
    expect(component.editableDraft()).toBe('Testo revisionato');
    fixture.destroy();
  }));
  it('saves a draft using the existing endpoint without changing the workflow status', fakeAsync(() => {
    const fixture = TestBed.createComponent(ReviewDashboardComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectEmail(example);
    component.editableDraft.set('Testo salvato');
    api.invoke.and.returnValue(
      Promise.resolve({ ...example, generated_draft: 'Testo salvato' }) as any,
    );
    component.saveDraft();
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(
      updateEmailDraftApiEmailsEmailIdDraftPut,
      {
        email_id: 'email-1',
        body: { generated_draft: 'Testo salvato', status: 'DRAFT' },
      },
    );
    expect(component.selectedEmail()?.generated_draft).toBe('Testo salvato');
    fixture.destroy();
  }));
  it('retains the editor after a Gmail failure and prevents repeated sends', fakeAsync(() => {
    const fixture = TestBed.createComponent(ReviewDashboardComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectEmail(example);
    component.editableDraft.set('Risposta revisionata');
    let complete!: (email: EmailResponse) => void;
    api.invoke.and.returnValue(
      new Promise<EmailResponse>((resolve) => (complete = resolve)) as any,
    );
    const before = api.invoke.calls.count();
    component.approveSelected();
    component.approveSelected();
    expect(api.invoke.calls.count()).toBe(before + 1);
    complete({
      ...example,
      status: 'FAILED',
      generated_draft: 'Risposta revisionata',
    });
    flushMicrotasks();
    fixture.detectChanges();
    expect(component.selectedEmail()?.status).toBe('FAILED');
    expect(fixture.nativeElement.querySelector('#email-draft').value).toBe(
      'Risposta revisionata',
    );
    expect(component.toast()?.error).toBeTrue();
    fixture.destroy();
  }));
  it('asks before discarding an unsaved draft and can keep the current email', fakeAsync(() => {
    const fixture = TestBed.createComponent(ReviewDashboardComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectEmail(example);
    component.editableDraft.set('Modifiche');
    spyOn(window, 'confirm').and.returnValue(false);
    component.setStatus('SENT');
    component.closeDetail();
    expect(component.selectedId()).toBe('email-1');
    expect(component.selectedStatus()).toBe('ALL');
    fixture.destroy();
  }));
});
