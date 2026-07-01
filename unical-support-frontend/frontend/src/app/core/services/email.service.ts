import { Injectable } from '@angular/core';
import { Api } from '../api/api';
import { readEmailsApiEmailsGet } from '../api/fn/emails/read-emails-api-emails-get';
import { readEmailApiEmailsEmailIdGet } from '../api/fn/emails/read-email-api-emails-email-id-get';
import { updateEmailDraftApiEmailsEmailIdDraftPut } from '../api/fn/emails/update-email-draft-api-emails-email-id-draft-put';
import { EmailResponse } from '../api/models/email-response';
import { EmailStatus } from '../api/models/email-status';
import { EmailUpdateDraft } from '../api/models/email-update-draft';

@Injectable({
  providedIn: 'root',
})
export class EmailService {
  constructor(private api: Api) {}

  getEmails(status?: EmailStatus | null): Promise<EmailResponse[]> {
    return this.api.invoke(readEmailsApiEmailsGet, { status: status ?? null, limit: 200 });
  }

  getEmail(email_id: string): Promise<EmailResponse> {
    return this.api.invoke(readEmailApiEmailsEmailIdGet, { email_id: email_id as any });
  }

  updateDraft(email_id: string, body: EmailUpdateDraft): Promise<EmailResponse> {
    return this.api.invoke(updateEmailDraftApiEmailsEmailIdDraftPut, {
      email_id: email_id as any,
      body,
    });
  }
}
