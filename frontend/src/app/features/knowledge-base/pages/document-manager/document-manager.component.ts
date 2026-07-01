import { Component, OnInit, ChangeDetectionStrategy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Api } from '../../../../core/api/api';
import { readDocumentsApiDocumentsGet } from '../../../../core/api/fn/documents/read-documents-api-documents-get';
import { deleteDocumentApiDocumentsDocumentIdDelete } from '../../../../core/api/fn/documents/delete-document-api-documents-document-id-delete';
import { DocumentResponse } from '../../../../core/api/models/document-response';

@Component({
  selector: 'app-document-manager',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './document-manager.component.html',
  styleUrl: './document-manager.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DocumentManagerComponent implements OnInit {
  private api = inject(Api);
  
  documents = signal<DocumentResponse[]>([]);
  loading = signal<boolean>(true);
  isDragging = signal<boolean>(false);

  ngOnInit() {
    this.loadDocuments();
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
  }

  handleFiles(files: FileList) {
    console.log('Uploading files', files);
    alert('Received ' + files.length + ' files. API integration pending.');
  }

  async deleteDocument(id: string) {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      await this.api.invoke(deleteDocumentApiDocumentsDocumentIdDelete, { document_id: id as any });
      this.documents.update(docs => docs.filter(d => d.id !== id));
    } catch (e) {
      console.error(e);
    }
  }
}
