import {
  Component,
  OnInit,
  OnDestroy,
  ChangeDetectionStrategy,
  signal,
  inject,
  computed,
  HostListener,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription, timer, from, exhaustMap } from 'rxjs';
import { CommonModule } from '@angular/common';
import { WorkspaceHeaderComponent } from '../../../../shared/components/workspace-header/workspace-header.component';
import { AutoResizeDirective } from '../../../../shared/components/auto-resize.directive';
import { DsIconComponent } from '../../../../shared/components/ds-icon/ds-icon.component';
import { AiConfidenceComponent } from '../../../../shared/components/ai-confidence/ai-confidence.component';
import { EmailPreviewComponent } from '../../../../shared/components/email-preview/email-preview.component';
import { DetailPanelDirective } from '../../../../shared/components/detail-panel.directive';
import { senderInfo } from '../../../../shared/sender';
import { EMAIL_STATUS_LABELS } from '../../../../shared/email-status-labels';
import { ShellUiService } from '../../../../core/services/shell-ui.service';
import { EditModalComponent } from '../../components/edit-modal/edit-modal.component';
import { Api } from '../../../../core/api/api';
import { readEmailPageApiEmailsPageGet } from '../../../../core/api/fn/emails/read-email-page-api-emails-page-get';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../../../../core/api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
import { LoadMoreDirective } from '../../../../shared/components/load-more.directive';
import { EmailPage } from '../../../../core/api/models/email-page';
import { readEmailApiEmailsEmailIdGet } from '../../../../core/api/fn/emails/read-email-api-emails-email-id-get';
import { retryFailedEmailApiEmailsEmailIdRetryPost } from '../../../../core/api/fn/emails/retry-failed-email-api-emails-email-id-retry-post';
import { retryFailedEmailBatchApiEmailsRetryFailedPost } from '../../../../core/api/fn/emails/retry-failed-email-batch-api-emails-retry-failed-post';
import { EmailResponse } from '../../../../core/api/models/email-response';
import { EmailFetchResponse } from '../../../../core/api/models/email-fetch-response';
import { fetchEmailsNowApiEmailsFetchNowPost } from '../../../../core/api/fn/emails/fetch-emails-now-api-emails-fetch-now-post';
import { readEmailFetchStatusApiEmailsFetchStatusJobIdGet } from '../../../../core/api/fn/emails/read-email-fetch-status-api-emails-fetch-status-job-id-get';

@Component({
  selector: 'app-review-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    WorkspaceHeaderComponent,
    DsIconComponent,
    AutoResizeDirective,
    LoadMoreDirective,
    DetailPanelDirective,
    AiConfidenceComponent,
    EmailPreviewComponent,
  ],
  templateUrl: './review-dashboard.component.html',
  styleUrl: './review-dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReviewDashboardComponent implements OnInit, OnDestroy {
  private api = inject(Api);
  private readonly shell = inject(ShellUiService);
  private readonly route = inject(ActivatedRoute, { optional: true });
  private readonly router = inject(Router, { optional: true });
  private filterSubscription?: Subscription;
  readonly senderInfo = senderInfo;
  readonly search = signal('');
  readonly selectedId = signal<string | null>(null);
  readonly editableDraft = signal('');
  readonly draftView = signal<'edit' | 'preview'>('edit');
  readonly acting = signal(false);
  readonly counts = this.shell.emailCounts;
  readonly statusLabels = EMAIL_STATUS_LABELS;
  private readonly openedEmail = signal<EmailResponse | null>(null);
  private readonly draftBase = signal('');
  readonly remoteEmail = signal<EmailResponse | null>(null);
  readonly selectedEmail = computed(() => this.openedEmail());
  readonly dirty = computed(() => !!this.selectedEmail() && this.editableDraft() !== this.draftBase());
  readonly total = signal(0);
  readonly nextCursor = signal<string | null>(null);
  readonly loadingMore = signal(false);
  readonly pageError = signal('');
  readonly retrying = signal(false);
  readonly pageSize = 50;
  private searchTimer?: ReturnType<typeof setTimeout>;
  readonly filteredEmails = computed(() => {
    const query = this.search().trim().toLocaleLowerCase('it');
    return this.emails().filter(
      (email) =>
        !query ||
        [
          email.sender,
          email.subject,
          email.body,
          ...(email.categories ?? []).map((category) => category.name),
        ]
          .join(' ')
          .toLocaleLowerCase('it')
          .includes(query),
    );
  });
  readonly groupedEmails = computed(() => {
    const groups = new Map<string, { key: string; label: string; emails: EmailResponse[] }>();
    const records = [...this.filteredEmails()].sort((a, b) => (b.received_at || '').localeCompare(a.received_at || '') || b.id.localeCompare(a.id));
    for (const email of records) {
      const key = this.dayKey(email.received_at);
      if (!groups.has(key)) groups.set(key, { key, label: this.dayLabel(key), emails: [] });
      groups.get(key)!.emails.push(email);
    }
    return [...groups.values()];
  });
  private dayKey(value?: string | null): string {
    if (!value || !Number.isFinite(Date.parse(value))) return 'unknown';
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(value));
    return ['year', 'month', 'day'].map(type => parts.find(part => part.type === type)!.value).join('-');
  }
  private dayLabel(key: string): string {
    if (key === 'unknown') return 'Data non disponibile';
    const today = this.dayKey(new Date().toISOString());
    if (key === today) return 'Oggi';
    const yesterday = new Date(today + 'T12:00:00Z'); yesterday.setUTCDate(yesterday.getUTCDate() - 1);
    if (key === yesterday.toISOString().slice(0, 10)) return 'Ieri';
    return new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(key + 'T12:00:00Z'));
  }
  arrivalTime(value?: string | null): string {
    return value ? new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '';
  }
  @HostListener('window:beforeunload', ['$event']) protectUnsavedDraft(event: BeforeUnloadEvent): void {
    if (this.dirty()) { event.preventDefault(); event.returnValue = ''; }
  }
  canLeave(): boolean { return !this.acting() && this.confirmDiscard(); }
  private remember(email: EmailResponse): void {
    this.openedEmail.set({ ...email });
    this.editableDraft.set(email.generated_draft || '');
    this.draftBase.set(email.generated_draft || '');
    this.remoteEmail.set(null);
  }
  private beginAction(): void {
    this.acting.set(true); ++this.loadSequence;
    this.refreshing = false; this.loadingMore.set(false); this.loading.set(false);
  }
  private closeSelection(): void { this.selectedId.set(null); this.openedEmail.set(null); this.remoteEmail.set(null); }
  private upsert(email: EmailResponse): void {
    this.emails.update(items => items.some(item => item.id === email.id) ? items.map(item => item.id === email.id ? email : item) : [email, ...items]);
  }
  async loadRemoteVersion(): Promise<void> {
    if (!this.confirmDiscard()) return;
    const fresh = this.remoteEmail();
    if (fresh) this.remember(fresh);
  }
  keepLocalVersion(): void {
    const remote = this.remoteEmail();
    if (!remote || !['DRAFT', 'ESCALATED', 'FAILED'].includes(remote.status)) return;
    this.openedEmail.set({ ...remote }); this.draftBase.set(remote.generated_draft || ''); this.remoteEmail.set(null);
    this.showToast('Testo locale conservato. Ora puoi salvare sulla revisione aggiornata.');
  }
  private compareRemote(fresh: EmailResponse): void {
    const opened = this.selectedEmail();
    if (!opened || fresh.id !== opened.id || (fresh.draft_revision ?? 0) < (opened.draft_revision ?? 0)) return;
    if (fresh.draft_revision !== opened.draft_revision || fresh.status !== opened.status || fresh.generated_draft !== opened.generated_draft) this.remoteEmail.set(fresh);
  }
  readonly canReview = computed(() =>
    ['DRAFT', 'ESCALATED', 'FAILED'].includes(
      this.selectedEmail()?.status ?? '',
    ),
  );
  selectEmail(email: EmailResponse): void {
    if (this.acting() || email.id === this.selectedId()) return;
    if (email.id !== this.selectedId() && !this.confirmDiscard()) return;
    this.draftView.set('edit');
    this.selectedId.set(email.id);
    this.remember(email);
  }
  closeDetail(): void {
    if (!this.acting() && this.confirmDiscard()) this.closeSelection();
  }
  private confirmDiscard(): boolean {
    return !this.dirty() || confirm('Chiudere la bozza senza salvare le modifiche?');
  }

  tone(status: string): string {
    return status === 'SENT'
      ? 'success'
      : status === 'FAILED' || status === 'ESCALATED'
        ? 'danger'
        : status === 'DRAFT' ||
            status === 'TO_RESPOND' ||
            status === 'TO_CLASSIFY'
          ? 'info'
          : 'warning';
  }
  needsAttention(status: string): boolean {
    return ['UNREAD', 'TO_CLASSIFY', 'ESCALATED', 'FAILED'].includes(status);
  }
  listStatusLabel(status: EmailResponse['status']): string {
    return status === 'DRAFT' ? 'Bozza pronta' : this.statusLabels[status];
  }
  initials(sender: string): string {
    return sender
      .replace(/<.*>/, '')
      .trim()
      .split(/[ .@_-]/)
      .filter(Boolean)
      .map((word) => word[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();
  }
  tabCount(status: string): number | null {
    return status === this.selectedStatus()
      ? this.emails().length
      : (this.counts()[status] ?? null);
  }
  private recordPage(page: EmailPage): void {
    this.total.set(page.total); this.counts.set(page.counts);
    this.shell.emailCount.set({ count: (page.counts['DRAFT'] ?? 0) + (page.counts['ESCALATED'] ?? 0), label: 'Bozze e email da gestire' });
  }
  async approveSelected(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || this.acting() || !this.editableDraft().trim()) return;
    this.beginAction();
    try {
      if (await this.handleApprove({ email, draft: this.editableDraft() })) this.closeSelection();
    } finally {
      this.acting.set(false);
      void this.loadEmails(false);
    }
  }
  async escalateSelected(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || this.acting()) return;
    this.beginAction();
    try {
      await this.handleEscalate({
        ...email,
        generated_draft: this.editableDraft(),
      });
    } finally {
      this.acting.set(false);
      void this.loadEmails(false);
    }
  }
  async saveDraft(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || this.acting() || !this.editableDraft().trim()) return;
    this.beginAction();
    try {
      const updated = await this.api.invoke(
        updateEmailDraftApiEmailsEmailIdDraftPut,
        {
          email_id: email.id,
          body: { generated_draft: this.editableDraft(), status: email.status, expected_revision: email.draft_revision ?? 0 },
        },
      );
      this.upsert(updated);
      this.remember(updated);
      this.showToast('Bozza salvata.');
    } catch (error: any) {
      await this.reportDraftError(error, 'Impossibile salvare la bozza. Le modifiche sono ancora disponibili.');
    } finally {
      this.acting.set(false);
    }
  }

  emails = signal<EmailResponse[]>([]);
  loading = signal<boolean>(true);
  fetching = signal(false);
  toast = signal<{ message: string; error: boolean; tone: 'success' | 'warning' | 'error' | 'info' } | null>(null);
  private pollSubscription?: Subscription;
  private refreshSubscription?: Subscription;
  private toastTimer?: ReturnType<typeof setTimeout>;
  private loadSequence = 0;
  private refreshing = false;
  private destroyed = false;

  statuses = [
    { value: 'DRAFT', label: 'Bozze' },
    { value: 'ESCALATED', label: 'Da gestire' },
    { value: 'TO_RESPOND', label: 'In elaborazione' },
    { value: 'FAILED', label: 'Errori' },
    { value: 'SENT', label: 'Inviate' },
    { value: 'ALL', label: 'Tutte' },
  ];
  selectedStatus = this.shell.emailStatus;
  readonly selectedStatusLabel = computed(
    () =>
      this.statuses.find((status) => status.value === this.selectedStatus())
        ?.label || '',
  );

  ngOnInit() {
    if (this.route) {
      let initial = true;
      this.filterSubscription = this.route.queryParamMap.subscribe((params) => {
        const requested = params.get('status') || 'ALL';
        const status = this.statuses.some((item) => item.value === requested)
          ? requested
          : 'ALL';
        if (initial) {
          initial = false;
          this.selectedStatus.set(status);
          this.loadEmails();
        } else if (
          status !== this.selectedStatus() &&
          !this.setStatus(status)
        ) {
          // Keep the URL and sidebar aligned when an edited draft must stay open.
          void this.router?.navigate([], {
            relativeTo: this.route,
            queryParams: { status: this.selectedStatus() },
            queryParamsHandling: 'merge',
            replaceUrl: true,
          });
        }
      });
    } else this.loadEmails();
    this.refreshSubscription = timer(5000, 5000).subscribe(() => {
      if (!this.loading()) this.loadEmails(false);
    });
  }

  ngOnDestroy() {
    this.destroyed = true;
    this.filterSubscription?.unsubscribe();
    this.pollSubscription?.unsubscribe();
    this.refreshSubscription?.unsubscribe();
    clearTimeout(this.toastTimer);
    clearTimeout(this.searchTimer);
    ++this.loadSequence;
  }

  showToast(message: string, error = false, tone: 'success' | 'warning' | 'error' | 'info' = error ? 'error' : 'success') {
    if (this.destroyed) return;
    clearTimeout(this.toastTimer);
    this.toast.set({ message, error, tone });
    this.toastTimer = setTimeout(() => this.toast.set(null), 8000);
  }

  async fetchEmails() {
    if (this.fetching()) return;
    this.fetching.set(true);
    try {
      const job = await this.api.invoke(
        fetchEmailsNowApiEmailsFetchNowPost,
        {},
      );
      if (this.destroyed) return;
      this.showToast(
        job.already_running
          ? 'Un controllo è già in corso. Attendo il risultato.'
          : 'Controllo delle nuove email avviato.',
        false, 'warning',
      );
      this.pollSubscription?.unsubscribe();
      this.pollSubscription = timer(0, 1500)
        .pipe(
          exhaustMap(() =>
            from(
              this.api.invoke(
                readEmailFetchStatusApiEmailsFetchStatusJobIdGet,
                { job_id: job.job_id },
              ),
            ),
          ),
        )
        .subscribe({
          next: (result: EmailFetchResponse) => {
            if (['completed', 'failed', 'expired'].includes(result.status)) {
              this.fetching.set(false);
              this.pollSubscription?.unsubscribe();
              this.showToast(result.message, result.status === 'failed', result.status === 'completed' ? 'success' : result.status === 'expired' ? 'warning' : 'error');
              this.loadEmails(false);
            }
          },
          error: () => {
            this.fetching.set(false);
            this.showToast(
              'Impossibile verificare il controllo email. Riprova tra poco.',
              true,
            );
          },
        });
    } catch {
      this.fetching.set(false);
      this.showToast(
        'Impossibile avviare il controllo delle email. Riprova tra poco.',
        true,
      );
    }
  }

  onSearch(value: string): void {
    this.search.set(value); clearTimeout(this.searchTimer);
    ++this.loadSequence; this.refreshing = false; this.loadingMore.set(false); this.nextCursor.set(null);
    this.searchTimer = setTimeout(() => { void this.loadEmails(); }, 300);
  }
  async loadEmails(showLoading = true): Promise<void> {
    if (!showLoading && (this.refreshing || this.loadingMore() || this.acting())) return;
    const sequence = ++this.loadSequence;
    this.refreshing = true;
    if (showLoading) { this.loading.set(true); this.nextCursor.set(null); this.loadingMore.set(false); }
    this.pageError.set('');
    try {
      const status = this.selectedStatus(), query = this.search().trim();
      const target = showLoading ? this.pageSize : Math.max(this.pageSize, this.emails().length);
      let cursor: string | null = null;
      let items: EmailResponse[] = [];
      let page!: EmailPage;
      do {
        page = await this.api.invoke(readEmailPageApiEmailsPageGet, {
          limit: this.pageSize, ...(status !== 'ALL' ? { status: status as any } : {}), ...(cursor ? { cursor } : {}), ...(query ? { q: query } : {}),
        });
        if (this.destroyed || sequence !== this.loadSequence) return;
        items = [...new Map([...items, ...page.items].map(item => [item.id, item])).values()];
        cursor = page.next_cursor || null;
      } while (cursor && items.length < target);
      if (this.destroyed || sequence !== this.loadSequence) return;
      this.emails.set(items); this.nextCursor.set(cursor); this.recordPage(page);
      const selected = this.selectedEmail();
      if (selected) {
        const fresh = items.find(item => item.id === selected.id) || await this.api.invoke(readEmailApiEmailsEmailIdGet, { email_id: selected.id }).catch(() => null);
        if (fresh && sequence === this.loadSequence && !this.destroyed) this.compareRemote(fresh);
      }
    } catch {
      if (sequence === this.loadSequence && showLoading) this.showToast('Impossibile caricare le email. Riprova tra poco.', true);
    } finally {
      if (sequence === this.loadSequence) { this.loading.set(false); this.refreshing = false; }
    }
  }
  async loadMore(): Promise<void> {
    const cursor = this.nextCursor();
    if (!cursor || this.loadingMore() || this.loading() || this.refreshing || this.acting()) return;
    const sequence = this.loadSequence;
    this.loadingMore.set(true); this.pageError.set('');
    try {
      const status = this.selectedStatus(), query = this.search().trim();
      const page = await this.api.invoke(readEmailPageApiEmailsPageGet, { limit: this.pageSize, cursor, ...(status !== 'ALL' ? { status: status as any } : {}), ...(query ? { q: query } : {}) });
      if (this.destroyed || sequence !== this.loadSequence) return;
      this.emails.update(items => [...new Map([...items, ...page.items].map(item => [item.id, item])).values()]);
      this.nextCursor.set(page.next_cursor || null); this.recordPage(page);
    } catch {
      if (sequence === this.loadSequence) this.pageError.set('Impossibile caricare altre email. Riprova.');
    } finally {
      if (sequence === this.loadSequence) this.loadingMore.set(false);
    }
  }
  private async reportDraftError(error: any, fallback: string): Promise<void> {
    this.showToast(error?.status === 409 ? 'La versione sul server è cambiata. Le modifiche locali sono conservate: confronta le versioni prima di salvare.' : fallback, true);
    const opened = this.selectedEmail();
    if (error?.status === 409 && opened) {
      try { this.compareRemote(await this.api.invoke(readEmailApiEmailsEmailIdGet, { email_id: opened.id })); } catch { /* keep local content */ }
    }
  }
  async retrySelected(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || email.status !== 'FAILED' || this.acting()) return;
    if (this.dirty()) { this.showToast('Salva le modifiche prima di riprovare l’elaborazione.', false, 'warning'); return; }
    this.beginAction();
    try {
      const updated = await this.api.invoke(retryFailedEmailApiEmailsEmailIdRetryPost, { email_id: email.id, body: { expected_revision: email.draft_revision ?? 0 } });
      this.upsert(updated); this.remember(updated);
      this.showToast('Elaborazione riavviata. La bozza precedente resta visibile fino al nuovo risultato.');
    } catch (error: any) { await this.reportDraftError(error, 'Impossibile riavviare l’elaborazione. La bozza è conservata.'); }
    finally { this.acting.set(false); void this.loadEmails(false); }
  }
  async retryFailed(): Promise<void> {
    if (this.retrying() || this.acting()) return;
    this.retrying.set(true);
    try {
      const selected = this.selectedEmail();
      const result = await this.api.invoke(retryFailedEmailBatchApiEmailsRetryFailedPost, { body: { exclude_ids: selected ? [selected.id] : [] } });
      this.showToast(`${result.queued_count ?? 0} email riaccodate. Le bozze revisionate e l’email aperta restano protette.${result.remaining_count ? ' Restano ' + result.remaining_count + ' email da riaccodare.' : ''}${result.failed_count ? ' Alcuni job non sono stati accodati: riprova.' : ''}`, !!result.failed_count, result.failed_count ? 'error' : 'success');
      await this.loadEmails(false);
    } catch { this.showToast('Impossibile riavviare le email in errore. Riprova.', true); }
    finally { this.retrying.set(false); }
  }

  setStatus(status: string): boolean {
    if (this.acting() || !this.confirmDiscard()) return false;
    this.closeSelection();
    this.selectedStatus.set(status);
    this.loadEmails();
    return true;
  }

  openModal(email: EmailResponse, modal: EditModalComponent) {
    modal.open(email);
  }

  async handleApprove(event: { email: EmailResponse; draft: string }) {
    try {
      const updated = await this.api.invoke(
        updateEmailDraftApiEmailsEmailIdDraftPut,
        {
          email_id: event.email.id as any,
          body: {
            generated_draft: event.draft,
            status: 'SENT' as any,
            expected_revision: event.email.draft_revision ?? 0,
          },
        },
      );
      if (updated.status === 'FAILED') {
        this.emails.update((emails) =>
          emails.map((e) => (e.id === updated.id ? updated : e)),
        );
        if (this.selectedId() === updated.id) this.remember(updated);
        this.showToast(
          'Invio non riuscito. La risposta è stata salvata: verifica la connessione alla posta e riprova.',
          true,
        );
        return false;
      }
      this.showToast('Risposta inviata.');
      this.emails.update((emails) =>
        emails.filter((e) => e.id !== event.email.id),
      );
      return true;
    } catch (error: any) {
      await this.reportDraftError(error, 'Errore durante l’invio della risposta.');
      return false;
    }
  }

  async handleEscalate(email: EmailResponse) {
    try {
      await this.api.invoke(updateEmailDraftApiEmailsEmailIdDraftPut, {
        email_id: email.id as any,
        body: {
          generated_draft: email.generated_draft || '',
          status: 'ESCALATED' as any,
          expected_revision: email.draft_revision ?? 0,
        },
      });
      this.emails.update((emails) => emails.filter((e) => e.id !== email.id));
      this.showToast('Email assegnata alla gestione manuale.', false, 'warning');
      this.closeSelection();
    } catch (error: any) {
      await this.reportDraftError(error, 'Impossibile richiedere la gestione manuale.');
    }
  }
}
