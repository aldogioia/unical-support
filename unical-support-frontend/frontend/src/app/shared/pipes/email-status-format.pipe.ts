import { Pipe, PipeTransform } from '@angular/core';
import { EmailStatus } from '../../core/api/models/email-status';

export interface StatusView {
  label: string;
  cssClass: 'valid' | 'invalid' | 'neutral';
}

const EMAIL_STATUS_MAP: Record<EmailStatus, StatusView> = {
  UNREAD: { label: 'Non letta', cssClass: 'invalid' },
  TO_CLASSIFY: { label: 'Da classificare', cssClass: 'invalid' },
  TO_RESPOND: { label: 'Da rispondere', cssClass: 'invalid' },
  DRAFT: { label: 'Bozza', cssClass: 'neutral' },
  ESCALATED: { label: 'Escalation', cssClass: 'invalid' },
  SENT: { label: 'Inviata', cssClass: 'valid' },
  IGNORED: { label: 'Ignorata', cssClass: 'neutral' },
  FAILED: { label: 'Errore', cssClass: 'invalid' },
};

@Pipe({
  name: 'emailStatusFormat',
  standalone: true,
})
export class EmailStatusFormatPipe implements PipeTransform {
  transform(status: EmailStatus | null | undefined): StatusView {
    if (!status) return { label: 'Sconosciuto', cssClass: 'neutral' };
    return EMAIL_STATUS_MAP[status] ?? { label: status, cssClass: 'neutral' };
  }
}
