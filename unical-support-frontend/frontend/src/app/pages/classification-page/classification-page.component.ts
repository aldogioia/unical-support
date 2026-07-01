import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import { LabelIcon, FilterMailCircleIcon, Refresh01Icon } from '@hugeicons/core-free-icons';
import { EmailService } from '../../core/services/email.service';
import { EmailResponse } from '../../core/api/models/email-response';
import { EmailListItemComponent } from '../../shared/components/email-list-item/email-list-item.component';
import { EmailStatusFormatPipe } from '../../shared/pipes/email-status-format.pipe';

@Component({
  selector: 'app-classification-page',
  standalone: true,
  imports: [CommonModule, HugeiconsIconComponent, EmailListItemComponent, EmailStatusFormatPipe],
  templateUrl: './classification-page.component.html',
  styleUrls: [
    './classification-page.component.css',
    '../../../../public/styles/layout.css',
    '../../../../public/styles/input.css',
  ],
})
export class ClassificationPageComponent implements OnInit {
  protected readonly Refresh01Icon = Refresh01Icon;
  protected readonly LabelIcon = LabelIcon;
  protected readonly FilterMailCircleIcon = FilterMailCircleIcon;

  protected emails: EmailResponse[] = [];
  protected skeletons: number[] = Array(15).fill(0);

  protected selectedEmail: EmailResponse | null = null;

  protected isFetching = false;
  protected isFiltered = false;

  constructor(
    private emailService: EmailService,
    private changeDetectorRef: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.getEmails();
  }

  getEmails() {
    this.isFetching = true;

    this.emailService.getEmails().then(
      emails => {
        this.emails = emails;
        this.isFetching = false;

        if (this.selectedEmail) {
          const updated = this.emails.find(e => e.id === this.selectedEmail?.id);
          if (updated) this.selectedEmail = updated;
        }

        this.changeDetectorRef.detectChanges();
      },
      () => {
        this.isFetching = false;
        this.changeDetectorRef.detectChanges();
        alert('Errore nel caricamento delle email');
      },
    );
  }

  selectEmail(email: EmailResponse) {
    this.selectedEmail = email;
  }
}
