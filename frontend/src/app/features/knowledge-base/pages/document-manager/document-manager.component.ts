import { Component, OnInit, ChangeDetectionStrategy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../../core/api/api';
import { readDocumentsApiDocumentsGet } from '../../../../core/api/fn/documents/read-documents-api-documents-get';
import { uploadDocumentApiDocumentsUploadPost } from '../../../../core/api/fn/documents/upload-document-api-documents-upload-post';
import { updateDocumentApiDocumentsDocumentIdPut } from '../../../../core/api/fn/documents/update-document-api-documents-document-id-put';
import { deleteDocumentApiDocumentsDocumentIdDelete } from '../../../../core/api/fn/documents/delete-document-api-documents-document-id-delete';
import { readCategoriesApiCategoriesGet } from '../../../../core/api/fn/categories/read-categories-api-categories-get';
import { DocumentResponse } from '../../../../core/api/models/document-response';
import { CategoryResponse } from '../../../../core/api/models/category-response';

@Component({
  selector: 'app-document-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './document-manager.component.html',
  styleUrl: './document-manager.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DocumentManagerComponent implements OnInit {
  private api = inject(Api);

  documents = signal<DocumentResponse[]>([]);
  categories = signal<CategoryResponse[]>([]);
  loading = signal<boolean>(true);
  isDragging = signal<boolean>(false);
  uploading = signal<boolean>(false);
  uploadError = signal<string | null>(null);

  // Categoria e link scelti nel form sopra la zona di drag & drop,
  // usati sia per l'upload di file sia per l'aggiunta di un link.
  selectedCategoryId = '';
  linkUrl = '';

  // Modifica inline della categoria su un documento già caricato
  editingCategoryDocId = signal<string | null>(null);
  savingCategoryDocId = signal<string | null>(null);

  startEditCategory(doc: DocumentResponse) {
    this.editingCategoryDocId.set(doc.id);
  }

  cancelEditCategory() {
    this.editingCategoryDocId.set(null);
  }

  async saveDocumentCategory(doc: DocumentResponse, newCategoryId: string) {
    this.savingCategoryDocId.set(doc.id);
    try {
      const updated = await this.api.invoke(updateDocumentApiDocumentsDocumentIdPut, {
        document_id: doc.id,
        body: { category_id: newCategoryId || null }
      });
      this.documents.update(docs => docs.map(d => d.id === doc.id ? updated : d));
      this.editingCategoryDocId.set(null);
    } catch (e) {
      console.error(e);
      alert('Errore durante l\'aggiornamento della categoria.');
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
    try {
      const data = await this.api.invoke(readDocumentsApiDocumentsGet, {});
      this.documents.set(data);
    } catch (e) {
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

  async handleFiles(files: FileList) {
    this.uploadError.set(null);
    this.uploading.set(true);
    const sourceLink = this.linkUrl.trim() || null;
    try {
      for (const file of Array.from(files)) {
        const created = await this.api.invoke(uploadDocumentApiDocumentsUploadPost, {
          body: {
            file: file as any,
            // Se è stato indicato un link, viene salvato come fonte del documento
            // (il testo viene comunque estratto dal file, non dal link).
            url: sourceLink as any,
            category_id: (this.selectedCategoryId || null) as any,
          }
        });
        this.documents.update(docs => [created, ...docs]);
      }
      this.linkUrl = '';
    } catch (e) {
      console.error(e);
      this.uploadError.set("Errore durante il caricamento del file. Riprova.");
    } finally {
      this.uploading.set(false);
    }
  }

  async addLink() {
    const url = this.linkUrl.trim();
    if (!url) return;

    this.uploadError.set(null);
    this.uploading.set(true);
    try {
      const created = await this.api.invoke(uploadDocumentApiDocumentsUploadPost, {
        body: {
          url,
          category_id: (this.selectedCategoryId || null) as any,
        }
      });
      this.documents.update(docs => [created, ...docs]);
      this.linkUrl = '';
    } catch (e) {
      console.error(e);
      this.uploadError.set("Errore durante l'aggiunta del link. Verifica che sia raggiungibile.");
    } finally {
      this.uploading.set(false);
    }
  }

  async deleteDocument(id: string) {
    if (!confirm('Sei sicuro di voler eliminare questo documento?')) return;
    try {
      await this.api.invoke(deleteDocumentApiDocumentsDocumentIdDelete, { document_id: id as any });
      this.documents.update(docs => docs.filter(d => d.id !== id));
    } catch (e) {
      console.error(e);
    }
  }
}