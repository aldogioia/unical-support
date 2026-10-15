import {
  Component,
  OnInit,
  OnDestroy,
  ChangeDetectionStrategy,
  signal,
  inject,
  computed,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription, timer, from, exhaustMap } from 'rxjs';
import { CommonModule } from '@angular/common';
import { WorkspaceHeaderComponent } from '../../../../shared/components/workspace-header/workspace-header.component';
import { DsIconComponent } from '../../../../shared/components/ds-icon/ds-icon.component';
import { DetailPanelDirective } from '../../../../shared/components/detail-panel.directive';
import { EMAIL_STATUS_LABELS } from '../../../../shared/email-status-labels';
import { ShellUiService } from '../../../../core/services/shell-ui.service';
import { EditModalComponent } from '../../components/edit-modal/edit-modal.component';
import { Api } from '../../../../core/api/api';
import { readEmailsApiEmailsGet } from '../../../../core/api/fn/emails/read-emails-api-emails-get';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../../../../core/api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
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
    DetailPanelDirective,
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
  readonly search = signal('');
  readonly selectedId = signal<string | null>(null);
  readonly editableDraft = signal('');
  readonly acting = signal(false);
  readonly counts = this.shell.emailCounts;
  readonly statusLabels = EMAIL_STATUS_LABELS;
  readonly selectedEmail = computed(
    () => this.emails().find((email) => email.id === this.selectedId()) ?? null,
  );
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
  readonly canReview = computed(() =>
    ['DRAFT', 'ESCALATED', 'FAILED'].includes(
      this.selectedEmail()?.status ?? '',
    ),
  );
  selectEmail(email: EmailResponse): void {
    if (this.acting() || email.id === this.selectedId()) return;
    if (email.id !== this.selectedId() && !this.confirmDiscard()) return;
    this.selectedId.set(email.id);
    this.editableDraft.set(email.generated_draft || '');
  }
  closeDetail(): void {
    if (!this.acting() && this.confirmDiscard()) this.selectedId.set(null);
  }
  private confirmDiscard(): boolean {
    const email = this.selectedEmail();
    return (
      !email ||
      this.editableDraft() === (email.generated_draft || '') ||
      confirm('Chiudere la bozza senza salvare le modifiche?')
    );
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
  private recordCounts(status: string, data: EmailResponse[]): void {
    this.counts.update((counts) => ({ ...counts, [status]: data.length }));
    if (status === 'ALL')
      this.counts.update((counts) =>
        Object.fromEntries([
          ...Object.entries(counts),
          ...this.statuses
            .filter((s) => s.value !== 'ALL')
            .map((s) => [
              s.value,
              data.filter((email) => email.status === s.value).length,
            ]),
        ]),
      );
    const known = this.counts();
    if (known['DRAFT'] !== undefined && known['ESCALATED'] !== undefined)
      this.shell.emailCount.set({
        count: known['DRAFT'] + known['ESCALATED'],
        label: 'Bozze e email da gestire nelle viste caricate',
      });
    else if (status === 'DRAFT' || status === 'ESCALATED')
      this.shell.emailCount.set({
        count: data.length,
        label:
          status === 'DRAFT'
            ? 'Bozze nella vista caricata'
            : 'Email da gestire nella vista caricata',
      });
  }
  async approveSelected(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || this.acting() || !this.editableDraft().trim()) return;
    this.acting.set(true);
    try {
      await this.handleApprove({ email, draft: this.editableDraft() });
      if (!this.selectedEmail()) this.selectedId.set(null);
    } finally {
      this.acting.set(false);
      this.recordCounts(this.selectedStatus(), this.emails());
    }
  }
  async escalateSelected(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || this.acting()) return;
    this.acting.set(true);
    try {
      await this.handleEscalate({
        ...email,
        generated_draft: this.editableDraft(),
      });
    } finally {
      this.acting.set(false);
      this.recordCounts(this.selectedStatus(), this.emails());
    }
  }
  async saveDraft(): Promise<void> {
    const email = this.selectedEmail();
    if (!email || this.acting() || !this.editableDraft().trim()) return;
    this.acting.set(true);
    try {
      const updated = await this.api.invoke(
        updateEmailDraftApiEmailsEmailIdDraftPut,
        {
          email_id: email.id,
          body: { generated_draft: this.editableDraft(), status: email.status },
        },
      );
      this.emails.update((emails) =>
        emails.map((item) => (item.id === updated.id ? updated : item)),
      );
      this.showToast('Bozza salvata.');
    } catch {
      this.showToast(
        'Impossibile salvare la bozza. Le modifiche sono ancora disponibili.',
        true,
      );
    } finally {
      this.acting.set(false);
    }
  }

  emails = signal<EmailResponse[]>([]);
  loading = signal<boolean>(true);
  fetching = signal(false);
  toast = signal<{ message: string; error: boolean } | null>(null);
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
  }

  showToast(message: string, error = false) {
    if (this.destroyed) return;
    clearTimeout(this.toastTimer);
    this.toast.set({ message, error });
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
              this.showToast(result.message, result.status !== 'completed');
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

  async loadEmails(showLoading = true) {
    if (!showLoading && this.refreshing) return;
    const sequence = ++this.loadSequence;
    this.refreshing = true;
    if (showLoading) this.loading.set(true);
    try {
      const status = this.selectedStatus();
      const params: any = status === 'ALL' ? {} : { status };
      const data = await this.api.invoke(readEmailsApiEmailsGet, params);
      if (!this.destroyed && sequence === this.loadSequence) {
        this.emails.set(data);
        this.recordCounts(status, data);
      }
    } catch (e) {
      console.error('Impossibile caricare le email', e);
      if (showLoading)
        this.showToast(
          'Impossibile caricare le email. Riprova tra poco.',
          true,
        );
    } finally {
      if (sequence === this.loadSequence) {
        this.loading.set(false);
        this.refreshing = false;
      }
    }
  }

  setStatus(status: string): boolean {
    if (this.acting() || !this.confirmDiscard()) return false;
    this.selectedId.set(null);
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
          },
        },
      );
      if (updated.status === 'FAILED') {
        this.emails.update((emails) =>
          emails.map((e) => (e.id === updated.id ? updated : e)),
        );
        this.showToast(
          'Invio non riuscito. La risposta è stata salvata: verifica Gmail e riprova.',
          true,
        );
        return;
      }
      this.showToast('Risposta inviata.');
      // Rimuovi dall'elenco corrente e ricarica
      this.emails.update((emails) =>
        emails.filter((e) => e.id !== event.email.id),
      );
    } catch (e) {
      console.error("Errore durante l'invio:", e);
      this.showToast('Errore durante l’invio della risposta.', true);
    }
  }

  async handleEscalate(email: EmailResponse) {
    try {
      await this.api.invoke(updateEmailDraftApiEmailsEmailIdDraftPut, {
        email_id: email.id as any,
        body: {
          generated_draft: email.generated_draft || '',
          status: 'ESCALATED' as any,
        },
      });
      this.emails.update((emails) => emails.filter((e) => e.id !== email.id));
      this.showToast('Email assegnata alla gestione manuale.');
    } catch (e) {
      console.error("Errore durante l'escalation:", e);
      this.showToast('Impossibile richiedere la gestione manuale.', true);
    }
  }
}
