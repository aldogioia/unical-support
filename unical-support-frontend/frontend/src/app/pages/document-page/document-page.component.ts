import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import {
  Cancel01Icon,
  Delete02Icon,
  DocumentAttachmentIcon,
  File02Icon,
  FileUploadIcon,
  FileViewIcon,
  Link01Icon,
} from '@hugeicons/core-free-icons';
import { CategoryService } from '../../core/services/category.service';
import { DocumentService } from '../../core/services/document.service';
import { CategoryResponse } from '../../core/api/models/category-response';
import { DocumentResponse } from '../../core/api/models/document-response';

@Component({
  selector: 'app-document-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, HugeiconsIconComponent],
  templateUrl: './document-page.component.html',
  styleUrls: [
    './document-page.component.css',
    '../../../../public/styles/layout.css',
    '../../../../public/styles/input.css',
  ],
})
export class DocumentPageComponent implements OnInit {

  protected readonly File02Icon = File02Icon;
  protected readonly DocumentAttachmentIcon = DocumentAttachmentIcon;
  protected readonly Cancel01Icon = Cancel01Icon;
  protected readonly Delete02Icon = Delete02Icon;
  protected readonly FileUploadIcon = FileUploadIcon;
  protected readonly FileViewIcon = FileViewIcon;
  protected readonly Link01Icon = Link01Icon;

  protected isFetching = false;
  protected isLoading = false;
  protected dragOver = false;

  protected uploadMode: 'file' | 'url' = 'file';

  protected categories: CategoryResponse[] = [];
  protected documents: DocumentResponse[] = [];
  protected skeletons: number[] = Array(5).fill(0);

  protected form: FormGroup;

  constructor(
    private categoryService: CategoryService,
    private formBuilder: FormBuilder,
    private changeDetectorRef: ChangeDetectorRef,
    private documentService: DocumentService,
  ) {
    this.form = this.formBuilder.group({
      categoryId: [''],
      url: [''],
      file: [null],
    });
  }

  get file(): File | null {
    return this.form.get('file')?.value || null;
  }

  get isUploadDisabled(): boolean {
    if (this.uploadMode === 'file') return !this.file;
    return !this.form.get('url')?.value;
  }

  ngOnInit(): void {
    this.loadDocuments();

    this.categoryService.getCategories().then(categories => (this.categories = categories));
  }

  private loadDocuments() {
    this.isFetching = true;
    this.documentService.getDocuments().then(
      documents => {
        this.isFetching = false;
        this.documents = documents;
        this.changeDetectorRef.detectChanges();
      },
      () => {
        this.isFetching = false;
        alert('Errore nel caricamento dei documenti');
      },
    );
  }

  setUploadMode(mode: 'file' | 'url') {
    this.uploadMode = mode;
    this.form.get('file')?.setValue(null);
    this.form.get('url')?.setValue('');
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver = false;

    const file = event.dataTransfer?.files[0];
    if (!file) return;
    this.form.get('file')?.setValue(file);
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files) return;
    this.form.get('file')?.setValue(input.files[0]);
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  removeFile() {
    this.form.get('file')?.setValue(null);
  }

  reset() {
    this.form.reset({ categoryId: '', url: '', file: null });
  }

  upload() {
    if (this.isUploadDisabled) return;

    this.isLoading = true;

    this.documentService.uploadDocument({
      file: this.uploadMode === 'file' ? this.file : null,
      url: this.uploadMode === 'url' ? this.form.value.url : null,
      category_id: this.form.value.categoryId || null,
    }).then(
      () => {
        alert('Documento caricato con successo');
        this.isLoading = false;
        this.reset();
        this.loadDocuments();
      },
      (err) => {
        console.error(err);
        alert("Errore durante l'upload del documento");
        this.isLoading = false;
      },
    );
  }

  deleteDocument(document: DocumentResponse): void {
    if (!document) return;

    if (confirm('Sei sicuro di voler eliminare questo documento?')) {
      this.isLoading = true;

      this.documentService.deleteDocument(document.id).then(
        () => {
          this.isLoading = false;
          this.documents = this.documents.filter(d => d.id !== document.id);
          this.changeDetectorRef.detectChanges();
        },
        (err) => {
          console.error(err);
          this.isLoading = false;
          alert("Errore durante l'eliminazione");
        },
      );
    }
  }
}
