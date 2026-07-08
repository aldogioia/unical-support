import { Component, ViewChild, ElementRef, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../core/api/api';
import { createUserFeedbackApiFeedbackPost } from '../../../core/api/fn/feedback/create-user-feedback-api-feedback-post';
import html2canvas from 'html2canvas';

@Component({
  selector: 'app-feedback-button',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './feedback-button.component.html',
  styleUrl: './feedback-button.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FeedbackButtonComponent {
  private api = inject(Api);
  private cdr = inject(ChangeDetectorRef);

  @ViewChild('feedbackDialog') dialogRef!: ElementRef<HTMLDialogElement>;

  // Form fields
  description = '';
  attachScreenshot = true;

  // Screenshot states
  screenshotUrl: string | null = null;
  screenshotBlob: Blob | null = null;

  // Method to clear screenshot
  clearScreenshot() {
    this.screenshotUrl = null;
    this.screenshotBlob = null;
    this.attachScreenshot = false;
    this.cdr.markForCheck();
  }
  // UI States
  isButtonVisible = true;
  isCapturing = false;
  loading = false;
  errorMsg: string | null = null;
  success = false;

  async startFeedbackFlow() {
    this.isCapturing = true;
    this.isButtonVisible = false;
    this.cdr.markForCheck();

    // Allow time for the button to disappear from the DOM before rendering the canvas
    setTimeout(async () => {
      try {
        const canvas = await html2canvas(document.body, {
          useCORS: true,
          logging: false,
          ignoreElements: (element) => {
            // Explicitly ignore feedback dialog if it's somehow in the DOM
            return element.tagName.toLowerCase() === 'dialog' || element.classList.contains('feedback-widget-container');
          }
        });

        this.screenshotUrl = canvas.toDataURL('image/png');

        // Convert canvas to blob for backend upload
        canvas.toBlob((blob) => {
          this.screenshotBlob = blob;
          this.cdr.markForCheck();
        }, 'image/png');

      } catch (error) {
        console.error('Failed to capture screenshot', error);
        this.screenshotUrl = null;
        this.screenshotBlob = null;
      } finally {
        this.isButtonVisible = true;
        this.isCapturing = false;
        this.cdr.markForCheck();
        this.openDialog();
      }
    }, 150);
  }

  private openDialog() {
    this.success = false;
    this.errorMsg = null;
    this.dialogRef.nativeElement.showModal();
    this.cdr.markForCheck();
  }

  closeDialog() {
    this.dialogRef.nativeElement.close();
    this.resetForm();
  }

  resetForm() {
    this.description = '';
    this.attachScreenshot = true;
    this.screenshotUrl = null;
    this.screenshotBlob = null;
    this.loading = false;
    this.errorMsg = null;
    this.success = false;
    this.cdr.markForCheck();
  }

  async submitFeedback(event: Event) {
    event.preventDefault();
    if (!this.description.trim()) {
      this.errorMsg = 'Per favore, inserisci una descrizione.';
      return;
    }

    this.loading = true;
    this.errorMsg = null;
    this.cdr.markForCheck();

    try {
      const imageFile = (this.attachScreenshot && this.screenshotBlob)
        ? this.screenshotBlob
        : null;

      // Create parameters for the api call
      const params = {
        body: {
          description: this.description,
          image: imageFile as any // cast to any to satisfy TS compiler (requires string | null, but RequestBuilder accepts Blob)
        }
      };

      await this.api.invoke(createUserFeedbackApiFeedbackPost, params);

      this.success = true;
      this.loading = false;
      this.cdr.markForCheck();

      // Automatically close dialog after 2 seconds on success
      setTimeout(() => {
        if (this.success) {
          this.closeDialog();
        }
      }, 2000);

    } catch (error: any) {
      console.error('Error submitting feedback', error);
      this.errorMsg = 'Errore durante l\'invio del feedback. Riprova più tardi.';
      this.loading = false;
      this.cdr.markForCheck();
    }
  }
}
