import { EmailPage } from '../../../../core/api/models/email-page';
import { EmailResponse } from '../../../../core/api/models/email-response';

export function emailPage(items: EmailResponse[], next_cursor: string | null = null, total = items.length): EmailPage {
  const counts: Record<string, number> = { ALL: total, DRAFT: 0, ESCALATED: 0, TO_RESPOND: 0, FAILED: 0, SENT: 0 };
  for (const email of items) counts[email.status] = (counts[email.status] ?? 0) + 1;
  return { items, next_cursor, total, counts };
}
