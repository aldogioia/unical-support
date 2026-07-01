import { Injectable } from '@angular/core';
import { Api } from '../api/api';
import { readTemplatesApiTemplatesGet } from '../api/fn/templates/read-templates-api-templates-get';
import { readPendingTemplatesApiTemplatesPendingGet } from '../api/fn/templates/read-pending-templates-api-templates-pending-get';
import { createTemplateApiTemplatesPost } from '../api/fn/templates/create-template-api-templates-post';
import { updateTemplateApiTemplatesTemplateIdPut } from '../api/fn/templates/update-template-api-templates-template-id-put';
import { deleteTemplateApiTemplatesTemplateIdDelete } from '../api/fn/templates/delete-template-api-templates-template-id-delete';
import { reviewTemplateApiTemplatesTemplateIdReviewPost } from '../api/fn/templates/review-template-api-templates-template-id-review-post';
import { TemplateResponse } from '../api/models/template-response';
import { TemplateCreate } from '../api/models/template-create';
import { TemplateUpdate } from '../api/models/template-update';

@Injectable({
  providedIn: 'root',
})
export class TemplateService {
  constructor(private api: Api) {}

  getTemplates(): Promise<TemplateResponse[]> {
    return this.api.invoke(readTemplatesApiTemplatesGet, { limit: 500 });
  }

  getPendingTemplates(): Promise<TemplateResponse[]> {
    return this.api.invoke(readPendingTemplatesApiTemplatesPendingGet, {});
  }

  createTemplate(body: TemplateCreate): Promise<TemplateResponse> {
    return this.api.invoke(createTemplateApiTemplatesPost, { body });
  }

  updateTemplate(template_id: string, body: TemplateUpdate): Promise<TemplateResponse> {
    return this.api.invoke(updateTemplateApiTemplatesTemplateIdPut, {
      template_id: template_id as any,
      body,
    });
  }

  deleteTemplate(template_id: string): Promise<void> {
    return this.api.invoke(deleteTemplateApiTemplatesTemplateIdDelete, { template_id: template_id as any });
  }

  reviewTemplate(template_id: string, action: 'approve' | 'reject'): Promise<TemplateResponse> {
    return this.api.invoke(reviewTemplateApiTemplatesTemplateIdReviewPost, {
      template_id: template_id as any,
      body: { action },
    });
  }
}
