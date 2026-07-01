import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import { FilterMailCircleIcon, Mail01Icon, Refresh01Icon } from '@hugeicons/core-free-icons';
import { EmailService } from '../../core/services/email.service';
import { EmailResponse } from '../../core/api/models/email-response';
import { EmailStatus } from '../../core/api/models/email-status';
import { EmailListItemComponent } from '../../shared/components/email-list-item/email-list-item.component';
import { EmailStatusFormatPipe } from '../../shared/pipes/email-status-format.pipe';

@Component({
  selector: 'app-answers-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, HugeiconsIconComponent, EmailListItemComponent, EmailStatusFormatPipe],
  templateUrl: './answers-page.component.html',
  styleUrls: [
    './answers-page.component.css',
    '../../../../public/styles/layout.css',
    '../../../../public/styles/input.css',
  ],
})
export class AnswersPageComponent implements OnInit {
  protected readonly Mail01Icon = Mail01Icon;
  protected readonly FilterMailCircleIcon = FilterMailCircleIcon;
  protected readonly Refresh01Icon = Refresh01Icon;

  protected readonly statusOptions: EmailStatus[] = ['DRAFT', 'SENT', 'ESCALATED', 'IGNORED'];

  protected emails: EmailResponse[] = [];
  protected skeletons: number[] = Array(15).fill(0);

  protected selectedEmail: EmailResponse | null = null;

  protected form: FormGroup;

  protected isLoading = false;
  protected isFetching = false;
  protected isFiltered = false;

  protected draftMaxLength = 5000;

  constructor(
    private emailService: EmailService,
    private formBuilder: FormBuilder,
    private changeDetectorRef: ChangeDetectorRef,
  ) {
    this.form = this.formBuilder.group({
      generated_draft: ['', [Validators.required, Validators.maxLength(this.draftMaxLength)]],
      status: ['DRAFT', Validators.required],
    });
  }

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

    this.form.setValue({
      generated_draft: email.generated_draft ?? '',
      status: email.status === 'TO_RESPOND' || email.status === 'UNREAD' || email.status === 'TO_CLASSIFY'
        ? 'DRAFT'
        : email.status,
    });
  }

  submit() {
    if (this.form.invalid || this.isLoading || !this.selectedEmail) return;

    this.isLoading = true;

    const formValue = this.form.value;

    this.emailService.updateDraft(this.selectedEmail.id, {
      generated_draft: formValue.generated_draft,
      status: formValue.status,
    }).then(
      updatedEmail => {
        this.isLoading = false;
        this.selectedEmail = updatedEmail;

        const idx = this.emails.findIndex(e => e.id === updatedEmail.id);
        if (idx >= 0) this.emails[idx] = updatedEmail;

        alert('Risposta salvata con successo');
        this.changeDetectorRef.detectChanges();
      },
      () => {
        this.isLoading = false;
        this.changeDetectorRef.detectChanges();
        alert("Errore durante il salvataggio della risposta");
      },
    );
  }
}
