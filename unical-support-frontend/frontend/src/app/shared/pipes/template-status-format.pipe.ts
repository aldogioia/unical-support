import { Pipe, PipeTransform } from '@angular/core';
import { TemplateStatus } from '../../core/api/models/template-status';
import { StatusView } from './email-status-format.pipe';

const TEMPLATE_STATUS_MAP: Record<TemplateStatus, StatusView> = {
  ACTIVE: { label: 'Attivo', cssClass: 'valid' },
  PENDING_APPROVAL: { label: 'In attesa di approvazione', cssClass: 'invalid' },
  REJECTED: { label: 'Rifiutato', cssClass: 'invalid' },
};

@Pipe({
  name: 'templateStatusFormat',
  standalone: true,
})
export class TemplateStatusFormatPipe implements PipeTransform {
  transform(status: TemplateStatus | null | undefined): StatusView {
    if (!status) return { label: 'Sconosciuto', cssClass: 'neutral' };
    return TEMPLATE_STATUS_MAP[status] ?? { label: status, cssClass: 'neutral' };
  }
}
