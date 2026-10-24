import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Api } from '../../../core/api/api';
import { previewEmailDraftApiEmailsEmailIdPreviewPost } from '../../../core/api/fn/emails/preview-email-draft-api-emails-email-id-preview-post';

@Component({
  selector: 'app-email-preview', standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (!draft().trim()) {
      <p class="preview-status" role="alert">Scrivi una risposta per visualizzare l’anteprima.</p>
    } @else {
    @if (loading()) { <p class="preview-status" role="status">Preparazione dell’anteprima…</p> }
    @if (error()) { <p class="preview-status" role="alert">{{ error() }}</p> }
    @if (document(); as html) {
      <iframe title="Anteprima del template email Unical Support" sandbox="allow-same-origin" referrerpolicy="no-referrer" scrolling="no" (load)="fitPreview($event)" [srcdoc]="html"></iframe>
    }
    }
  `,
  styles: [`
    :host{display:block;min-width:0}
    iframe{display:block;width:100%;height:1px;overflow:hidden;border:1px solid var(--ds-control-border);border-radius:8px;background:#f5f5f4}
    .preview-status{padding:16px;color:var(--ds-text-secondary);font-size:12px}
  `],
})
export class EmailPreviewComponent {
  readonly emailId = input.required<string>();
  readonly draft = input.required<string>();
  readonly document = signal<SafeHtml | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  private readonly api = inject(Api);
  private readonly sanitizer = inject(DomSanitizer);

  private resizeObserver?: ResizeObserver;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.resizeObserver?.disconnect());
    effect(onCleanup => {
      const emailId = this.emailId();
      const draft = this.draft();
      let cancelled = false;
      this.resizeObserver?.disconnect();
      this.document.set(null);
      this.error.set('');
      this.loading.set(!!draft.trim());
      const timer = draft.trim() ? setTimeout(async () => {
        try {
          const result = await this.api.invoke(previewEmailDraftApiEmailsEmailIdPreviewPost, {
            email_id: emailId, body: { generated_draft: draft },
          });
          if (!cancelled) {
            // Keep scripts blocked. Same-origin access lets the parent measure the renderer's document.
            const parsed = new DOMParser().parseFromString(result.html, 'text/html');
            const policy = parsed.createElement('meta');
            policy.httpEquiv = 'Content-Security-Policy';
            policy.content = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'";
            parsed.head.prepend(policy);
            this.document.set(this.sanitizer.bypassSecurityTrustHtml('<!doctype html>' + parsed.documentElement.outerHTML));
          }
        } catch {
          if (!cancelled) this.error.set('Anteprima non disponibile. Torna alla modifica e riprova.');
        } finally {
          if (!cancelled) this.loading.set(false);
        }
      }, 300) : undefined;
      onCleanup(() => { cancelled = true; clearTimeout(timer); });
    }, { allowSignalWrites: true });
  }

  fitPreview(event: Event): void {
    const frame = event.target as HTMLIFrameElement;
    this.resizeObserver?.disconnect();
    try {
      const body = frame.contentDocument?.body;
      if (!body) return;
      const fit = () => {
        const height = Math.ceil(Math.max(body.scrollHeight, body.getBoundingClientRect().height));
        if (height) frame.style.height = `${height + frame.offsetHeight - frame.clientHeight}px`;
      };
      // Body height tracks paragraphs, lists, images and line reflow when the panel changes width.
      this.resizeObserver = new ResizeObserver(fit);
      this.resizeObserver.observe(body);
      fit();
    } catch {
      // A user may navigate a source link to another origin; never inspect that document.
    }
  }

}
