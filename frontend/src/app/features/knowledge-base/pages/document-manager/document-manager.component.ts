import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  signal,
  inject,
  computed,
  OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DsIconComponent } from '../../../../shared/components/ds-icon/ds-icon.component';
import { WorkspaceHeaderComponent } from '../../../../shared/components/workspace-header/workspace-header.component';
import { DetailPanelDirective } from '../../../../shared/components/detail-panel.directive';
import { Api } from '../../../../core/api/api';
import { readDocumentsApiDocumentsGet } from '../../../../core/api/fn/documents/read-documents-api-documents-get';
import { uploadDocumentApiDocumentsUploadPost } from '../../../../core/api/fn/documents/upload-document-api-documents-upload-post';
import { updateDocumentApiDocumentsDocumentIdPut } from '../../../../core/api/fn/documents/update-document-api-documents-document-id-put';
import { deleteDocumentApiDocumentsDocumentIdDelete } from '../../../../core/api/fn/documents/delete-document-api-documents-document-id-delete';
import { readCategoriesApiCategoriesGet } from '../../../../core/api/fn/categories/read-categories-api-categories-get';
import { DocumentResponse } from '../../../../core/api/models/document-response';
import { CategoryResponse } from '../../../../core/api/models/category-response';
import { CategoryMultiSelectComponent } from '../../../../shared/components/category-multi-select/category-multi-select.component';
import { forceIndexDocumentApiDocumentsDocumentIdForceIndexPost } from '../../../../core/api/fn/documents/force-index-document-api-documents-document-id-force-index-post';
import { AuthService } from '../../../../core/services/auth.service';

/** Una riga delle note di revisione prodotte dalla verifica di fedeltà. */
export interface ReviewPart {
  label: string;
  lost: string[];
  extra: string[];
  raw: string;
}

/** Deve coincidere con FORCED_REVIEW_NOTE in app/services/document_service.py. */
export const FORCED_REVIEW_NOTE =
  'Indicizzato manualmente da un amministratore nonostante la verifica di fedeltà.';
const REVIEW_POLL_MS = 3000;

/** Tipi accettati dal backend, ricavati dall'estensione quando il browser non li conosce. */
const MIME_BY_EXTENSION: Record<string, string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  txt: 'text/plain',
  md: 'text/markdown',
  json: 'application/json',
  yaml: 'application/x-yaml',
  yml: 'application/x-yaml',
};

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : '';
}

/**
 * Alcuni browser (Firefox su Windows per i .md) dichiarano un tipo generico:
 * in quel caso il tipo viene impostato in base all'estensione.
 */
export function withKnownType(file: File): File {
  const known = MIME_BY_EXTENSION[fileExtension(file.name)];
  if (!known || (file.type && file.type !== 'application/octet-stream')) return file;
  return new File([file], file.name, { type: known, lastModified: file.lastModified });
}
const REVIEW_POLL_MAX = 60;

export function parseReviewNotes(notes: string | null | undefined): ReviewPart[] {
  return (notes ?? '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && line !== FORCED_REVIEW_NOTE)
    .map((line) => {
      const match = /^Parte (\d+)\/(\d+):\s*(.*)$/.exec(line);
      const part: ReviewPart = {
        label: match ? `Parte ${match[1]} di ${match[2]}` : 'Nota',
        lost: [],
        extra: [],
        raw: line,
      };
      for (const segment of (match ? match[3] : line).split(/;\s*(?=dati )/)) {
        const lost = /^dati persi:\s*(.*)$/.exec(segment);
        const extra = /^dati non presenti nell'originale:\s*(.*)$/.exec(segment);
        const items = (lost ?? extra)?.[1].split(', ').map((s) => s.trim()).filter(Boolean) ?? [];
        if (lost) part.lost.push(...items);
        if (extra) part.extra.push(...items);
      }
      return part;
    });
}

@Component({
  selector: 'app-document-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CategoryMultiSelectComponent,
    DsIconComponent,
    WorkspaceHeaderComponent,
    DetailPanelDirective,
  ],
  templateUrl: './document-manager.component.html',
  styleUrl: './document-manager.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DocumentManagerComponent implements OnInit, OnDestroy {
  private api = inject(Api);
  private auth = inject(AuthService);
  readonly isAdmin = computed(() => this.auth.currentUser()?.role === 'admin');
  readonly reviewParts = computed(() =>
    parseReviewNotes(this.selectedDocument()?.review_notes),
  );
  readonly reviewHasExtra = computed(() =>
    this.reviewParts().some((part) => part.extra.length > 0),
  );
  readonly confirmingForceId = signal<string | null>(null);
  readonly forcingIds = signal<ReadonlySet<string>>(new Set());
  readonly reviewError = signal<string | null>(null);
  readonly reviewNotice = signal('');
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private pollAttempts = 0;
  readonly search = signal('');
  readonly selectedDocumentId = signal<string | null>(null);
  readonly creating = signal(false);
  readonly loadError = signal('');
  readonly uploadNotice = signal('');
  readonly selectedDocument = computed(
    () =>
      this.documents().find(
        (document) => document.id === this.selectedDocumentId(),
      ) ?? null,
  );
  readonly filteredDocuments = computed(() => {
    const query = this.search().trim().toLocaleLowerCase('it');
    return this.documents().filter(
      (document) =>
        (!query ||
          [
            document.filename,
            document.reference_url,
            document.extracted_text,
            ...(document.categories ?? []).map((c) => c.name),
          ]
            .join(' ')
            .toLocaleLowerCase('it')
            .includes(query)),
    );
  });
  openCreate(): void {
    if (this.uploading()) return;
    if (this.pendingFiles().length && !this.confirmDiscardQueue()) return;
    this.resetQueue();
    this.cancelEditCategories();
    this.selectedDocumentId.set(null);
    this.creating.set(true);
    this.uploadError.set(null);
    this.uploadNotice.set('');
  }
  selectDocument(document: DocumentResponse): void {
    if (this.uploading() || this.savingCategoryDocId()) return;
    if (this.pendingFiles().length && !this.confirmDiscardQueue()) return;
    this.resetQueue();
    this.resetReview();
    this.cancelEditCategories();
    this.creating.set(false);
    this.selectedDocumentId.set(document.id);
    this.startEditCategories(document);
  }
  closeDetail(): void {
    if (this.uploading() || this.savingCategoryDocId()) return;
    if (this.pendingFiles().length && !this.confirmDiscardQueue()) return;
    this.resetQueue();
    this.resetReview();
    this.cancelEditCategories();
    this.creating.set(false);
    this.selectedDocumentId.set(null);
  }
  format(document: DocumentResponse): string {
    return (
      document.filename.split('.').pop()?.toUpperCase().slice(0, 5) || 'FILE'
    );
  }

  /** File scelti e non ancora inviati: si inviano uno alla volta con il pulsante Invia. */
  readonly pendingFiles = signal<File[]>([]);
  readonly queueTotal = signal(0);
  readonly queueSent = signal(0);
  readonly currentFile = computed(() => this.pendingFiles()[0] ?? null);
  readonly queuePosition = computed(
    () => this.queueTotal() - this.pendingFiles().length + 1,
  );

  documents = signal<DocumentResponse[]>([]);
  categories = signal<CategoryResponse[]>([]);
  loading = signal<boolean>(true);
  isDragging = signal<boolean>(false);
  uploading = signal<boolean>(false);
  uploadError = signal<string | null>(null);

  // Metadata for local file uploads. The source link is never downloaded.
  selectedCategoryIds: string[] = [];
  referenceUrl = '';

  private validatePublicUrl(value: string, editing = false): boolean {
    if (!value.trim()) return true;
    try {
      const url = new URL(value.trim());
      if (
        !['http:', 'https:'].includes(url.protocol) ||
        url.username ||
        url.password ||
        value.trim().length > 2048
      )
        throw new Error();
      return true;
    } catch {
      (editing ? this.editError : this.uploadError).set(
        'Inserisci un URL valido che inizi con http:// o https://, senza credenziali.',
      );
      return false;
    }
  }

  // Modifica inline delle categorie su un documento già caricato
  editingCategoryDocId = signal<string | null>(null);
  savingCategoryDocId = signal<string | null>(null);
  editingCategoryIds: string[] = [];
  editingReferenceUrl = '';
  readonly editError = signal<string | null>(null);
  readonly editNotice = signal('');

  startEditCategories(doc: DocumentResponse) {
    this.editingCategoryIds = (doc.categories ?? []).map((c) => c.id);
    this.editingReferenceUrl = doc.reference_url ?? '';
    this.editError.set(null);
    this.editNotice.set('');
    this.editingCategoryDocId.set(doc.id);
  }

  cancelEditCategories() {
    this.editingCategoryDocId.set(null);
    this.editingCategoryIds = [];
    this.editingReferenceUrl = '';
    this.editError.set(null);
    this.editNotice.set('');
  }

  async saveDocumentCategories(doc: DocumentResponse) {
    if (
      this.savingCategoryDocId() ||
      !this.validatePublicUrl(this.editingReferenceUrl, true)
    )
      return;
    this.editError.set(null);
    this.editNotice.set('');
    this.savingCategoryDocId.set(doc.id);
    try {
      const updated = await this.api.invoke(
        updateDocumentApiDocumentsDocumentIdPut,
        {
          document_id: doc.id,
          body: {
            category_ids: [...this.editingCategoryIds],
            reference_url: this.editingReferenceUrl.trim() || null,
          },
        },
      );
      this.documents.update((docs) =>
        docs.map((d) => (d.id === doc.id ? updated : d)),
      );
      this.startEditCategories(updated);
      this.editNotice.set('Modifiche salvate.');
    } catch (e) {
      console.error(e);
      this.editError.set('Impossibile salvare le modifiche. Riprova.');
    } finally {
      this.savingCategoryDocId.set(null);
    }
  }

  ngOnInit() {
    this.loadDocuments();
    this.loadCategories();
  }

  async loadDocuments() {
    this.loading.set(true);
    this.loadError.set('');
    try {
      const data = await this.api.invoke(readDocumentsApiDocumentsGet, {});
      this.documents.set(data);
    } catch (e) {
      this.loadError.set('Impossibile caricare i documenti. Riprova.');
      console.error(e);
    } finally {
      this.loading.set(false);
    }
  }

  async loadCategories() {
    try {
      const data = await this.api.invoke(readCategoriesApiCategoriesGet, {});
      this.categories.set(data);
    } catch (e) {
      console.error(e);
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFiles(files);
    }
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFiles(input.files);
    }
    // reset per permettere di ricaricare lo stesso file una seconda volta
    input.value = '';
  }

  handleFiles(files: FileList | File[]) {
    if (this.uploading()) return;
    this.uploadNotice.set('');
    this.uploadError.set(null);
    const chosen = Array.from(files);
    const valid = chosen.filter((f) => fileExtension(f.name) in MIME_BY_EXTENSION);
    const rejected = chosen.length - valid.length;
    if (rejected) {
      this.uploadError.set(
        `${rejected === 1 ? 'Un file è stato scartato' : rejected + ' file sono stati scartati'}: formati ammessi PDF, DOCX, TXT, JSON, YAML, MD.`,
      );
    }
    if (!valid.length) return;
    if (!this.pendingFiles().length) {
      this.queueTotal.set(0);
      this.queueSent.set(0);
      this.clearUploadFields();
    }
    this.pendingFiles.update((queue) => [...queue, ...valid]);
    this.queueTotal.update((n) => n + valid.length);
  }

  /** Invia il file corrente con le sue categorie e il suo link, poi passa al successivo. */
  async sendCurrentFile() {
    const file = this.currentFile();
    if (!file || this.uploading()) return;
    this.uploadNotice.set('');
    this.uploadError.set(null);
    if (!this.validatePublicUrl(this.referenceUrl)) return;
    this.uploading.set(true);
    try {
      const created = await this.api.invoke(
        uploadDocumentApiDocumentsUploadPost,
        {
          body: {
            file: withKnownType(file) as any,
            reference_url: this.referenceUrl.trim() || null,
            category_ids: [...this.selectedCategoryIds],
          },
        },
      );
      this.documents.update((docs) => [created, ...docs]);
      this.queueSent.update((n) => n + 1);
      this.advanceQueue();
    } catch (e) {
      console.error(e);
      this.uploadError.set(
        `Invio di «${file.name}» non riuscito. Controlla il file e riprova: gli altri file restano in coda.`,
      );
    } finally {
      this.uploading.set(false);
    }
  }

  /** Toglie dalla coda il file corrente senza inviarlo. */
  skipCurrentFile() {
    if (!this.currentFile() || this.uploading()) return;
    this.uploadError.set(null);
    this.advanceQueue();
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private advanceQueue() {
    this.pendingFiles.update((queue) => queue.slice(1));
    this.clearUploadFields();
    if (this.pendingFiles().length) return;
    const sent = this.queueSent();
    this.queueTotal.set(0);
    this.queueSent.set(0);
    if (sent) {
      this.uploadNotice.set(
        sent === 1
          ? 'Documento inviato: è in elaborazione.'
          : `${sent} documenti inviati: sono in elaborazione.`,
      );
    }
  }

  private clearUploadFields() {
    this.selectedCategoryIds = [];
    this.referenceUrl = '';
  }

  private resetQueue() {
    this.pendingFiles.set([]);
    this.queueTotal.set(0);
    this.queueSent.set(0);
    this.clearUploadFields();
  }

  private confirmDiscardQueue(): boolean {
    const left = this.pendingFiles().length;
    return confirm(
      left === 1
        ? "C'è un file non ancora inviato: verrà scartato. Vuoi chiudere?"
        : `Ci sono ${left} file non ancora inviati: verranno scartati. Vuoi chiudere?`,
    );
  }

  needsReview(doc: DocumentResponse): boolean {
    return doc.processing_status === 'needs_review';
  }

  isForcing(doc: DocumentResponse): boolean {
    return this.forcingIds().has(doc.id);
  }

  wasForced(doc: DocumentResponse): boolean {
    return (
      doc.processing_status === 'indexed' &&
      !!doc.review_notes?.startsWith(FORCED_REVIEW_NOTE)
    );
  }

  askForceIndex(doc: DocumentResponse): void {
    this.reviewError.set(null);
    this.reviewNotice.set('');
    this.confirmingForceId.set(doc.id);
  }

  cancelForceIndex(): void {
    this.confirmingForceId.set(null);
  }

  async forceIndex(doc: DocumentResponse): Promise<void> {
    if (!this.isAdmin() || this.isForcing(doc)) return;
    this.confirmingForceId.set(null);
    this.reviewError.set(null);
    this.reviewNotice.set('');
    this.setForcing(doc.id, true);
    try {
      const updated = await this.api.invoke(
        forceIndexDocumentApiDocumentsDocumentIdForceIndexPost,
        { document_id: doc.id },
      );
      this.documents.update((docs) =>
        docs.map((d) => (d.id === doc.id ? updated : d)),
      );
      this.pollAttempts = 0;
      this.schedulePoll();
    } catch (e) {
      console.error(e);
      this.setForcing(doc.id, false);
      this.reviewError.set(
        "Impossibile avviare l'indicizzazione. Ricarica la pagina e riprova.",
      );
    }
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  private resetReview(): void {
    this.confirmingForceId.set(null);
    this.reviewError.set(null);
    this.reviewNotice.set('');
  }

  private setForcing(id: string, active: boolean): void {
    this.forcingIds.update((ids) => {
      const next = new Set(ids);
      if (active) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  private stopPolling(): void {
    if (this.pollTimer) clearTimeout(this.pollTimer);
    this.pollTimer = null;
  }

  private schedulePoll(): void {
    this.stopPolling();
    if (!this.forcingIds().size) return;
    if (this.pollAttempts >= REVIEW_POLL_MAX) {
      this.forcingIds.set(new Set());
      this.reviewNotice.set(
        "L'indicizzazione sta richiedendo più tempo del previsto: ricarica la pagina tra qualche minuto.",
      );
      return;
    }
    this.pollAttempts++;
    this.pollTimer = setTimeout(() => this.refreshForced(), REVIEW_POLL_MS);
  }

  private async refreshForced(): Promise<void> {
    this.pollTimer = null;
    try {
      const data = await this.api.invoke(readDocumentsApiDocumentsGet, {});
      this.documents.set(data);
      for (const id of this.forcingIds()) {
        const doc = data.find((d) => d.id === id);
        if (doc?.processing_status === 'pending') continue;
        this.setForcing(id, false);
        if (doc?.processing_status === 'indexed') {
          this.reviewNotice.set(
            `«${doc.filename}» è stato indicizzato: l'AI ora può usarlo nelle risposte.`,
          );
        } else if (doc?.processing_status === 'needs_review') {
          this.reviewError.set(
            `Indicizzazione di «${doc.filename}» non riuscita: il documento è tornato in revisione. Riprova più tardi.`,
          );
        }
      }
    } catch (e) {
      console.error(e);
    }
    this.schedulePoll();
  }

  async deleteDocument(id: string) {
    if (!confirm('Sei sicuro di voler eliminare questo documento?')) return;
    try {
      await this.api.invoke(deleteDocumentApiDocumentsDocumentIdDelete, {
        document_id: id as any,
      });
      this.documents.update((docs) => docs.filter((d) => d.id !== id));
    } catch (e) {
      console.error(e);
    }
  }
}
