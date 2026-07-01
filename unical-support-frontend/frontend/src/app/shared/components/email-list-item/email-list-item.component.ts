import { Component, Input } from '@angular/core';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import { Mail01Icon } from '@hugeicons/core-free-icons';
import { EmailResponse } from '../../../core/api/models/email-response';
import { EmailStatusFormatPipe } from '../../pipes/email-status-format.pipe';

@Component({
  selector: 'app-email-list-item',
  standalone: true,
  imports: [HugeiconsIconComponent, EmailStatusFormatPipe],
  templateUrl: './email-list-item.component.html',
  styleUrls: ['./email-list-item.component.css', '../../../../../public/styles/email-item.css'],
})
export class EmailListItemComponent {
  @Input({ required: true }) email!: EmailResponse;
  @Input({ required: true }) isSelected!: boolean;

  protected readonly Mail01Icon = Mail01Icon;
}
