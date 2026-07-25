import { Component, OnInit, ChangeDetectionStrategy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TaskCardComponent } from '../../../../shared/components/task-card/task-card.component';
import { EditModalComponent } from '../../components/edit-modal/edit-modal.component';
import { Api } from '../../../../core/api/api';
import { readEmailsApiEmailsGet } from '../../../../core/api/fn/emails/read-emails-api-emails-get';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../../../../core/api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
import { EmailResponse } from '../../../../core/api/models/email-response';

@Component({
  selector: 'app-review-dashboard',
  standalone: true,
  imports: [CommonModule, TaskCardComponent, EditModalComponent],
  templateUrl: './review-dashboard.component.html',
  styleUrl: './review-dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ReviewDashboardComponent implements OnInit {
  private api = inject(Api);
  
  emails = signal<EmailResponse[]>([]);
  loading = signal<boolean>(true);
  
  statuses = [
    { value: 'DRAFT', label: 'Drafts' },
    { value: 'ESCALATED', label: 'Escalated' },
    { value: 'TO_RESPOND', label: 'To Respond' },
    { value: 'SENT', label: 'Sent' },
    { value: 'ALL', label: 'All' }
  ];
  selectedStatus = signal<string>('DRAFT');

  ngOnInit() {
    this.loadEmails();
  }

  async loadEmails() {
    this.loading.set(true);
    try {
      const status = this.selectedStatus();
      const params: any = status === 'ALL' ? {} : { status };
      const data = await this.api.invoke(readEmailsApiEmailsGet, params);
      this.emails.set(data);
    } catch (e) {
      console.error('Failed to load emails', e);
    } finally {
      this.loading.set(false);
    }
  }

  setStatus(status: string) {
    this.selectedStatus.set(status);
    this.loadEmails();
  }

  openModal(email: EmailResponse, modal: EditModalComponent) {
    modal.open(email);
  }

  async handleApprove(event: {email: EmailResponse, draft: string}) {
    try {
      await this.api.invoke(updateEmailDraftApiEmailsEmailIdDraftPut, {
        email_id: event.email.id as any,
        body: {
          generated_draft: event.draft,
          status: 'SENT' as any,
        }
      });
      // Rimuovi dall'elenco corrente e ricarica
      this.emails.update(emails => emails.filter(e => e.id !== event.email.id));
    } catch (e) {
      console.error('Errore durante l\'invio:', e);
    }
  }

  async handleEscalate(email: EmailResponse) {
    try {
      await this.api.invoke(updateEmailDraftApiEmailsEmailIdDraftPut, {
        email_id: email.id as any,
        body: {
          generated_draft: email.generated_draft || '',
          status: 'ESCALATED' as any,
        }
      });
      this.emails.update(emails => emails.filter(e => e.id !== email.id));
    } catch (e) {
      console.error('Errore durante l\'escalation:', e);
    }
  }
}