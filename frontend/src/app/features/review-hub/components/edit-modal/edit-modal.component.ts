import { Component, Input, Output, EventEmitter, ViewChild, ElementRef, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EmailResponse } from '../../../../core/api/models/email-response';

@Component({
  selector: 'app-edit-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './edit-modal.component.html',
  styleUrl: './edit-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class EditModalComponent {
  @ViewChild('modal') modalRef!: ElementRef<HTMLDialogElement>;
  private cdr = inject(ChangeDetectorRef);
  
  @Input() email: EmailResponse | null = null;
  @Output() approve = new EventEmitter<{email: EmailResponse, draft: string}>();
  @Output() escalate = new EventEmitter<EmailResponse>();
  @Output() closed = new EventEmitter<void>();

  editableDraft = '';

  open(email: EmailResponse) {
    this.email = email;
    this.editableDraft = email.generated_draft || '';
    this.cdr.markForCheck();
    this.modalRef.nativeElement.showModal();
  }

  close() {
    this.modalRef.nativeElement.close();
    this.closed.emit();
    this.email = null;
  }

  onApprove() {
    if (this.email) {
      this.approve.emit({ email: this.email, draft: this.editableDraft });
      this.close();
    }
  }

  onEscalate() {
    if (this.email) {
      this.escalate.emit(this.email);
      this.close();
    }
  }
}
