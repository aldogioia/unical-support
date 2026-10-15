import { EmailStatus } from '../core/api/models/email-status';

export const EMAIL_STATUS_LABELS: Record<EmailStatus, string> = {
  UNREAD: 'Non letta',
  TO_CLASSIFY: 'Da classificare',
  TO_RESPOND: 'In elaborazione',
  DRAFT: 'Bozza',
  ESCALATED: 'Da gestire',
  SENT: 'Inviata',
  IGNORED: 'Ignorata',
  FAILED: 'Errore',
};
