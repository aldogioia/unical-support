import { Injectable } from '@angular/core';
import { Api } from '../api/api';
import { readDocumentsApiDocumentsGet } from '../api/fn/documents/read-documents-api-documents-get';
import { uploadDocumentApiDocumentsUploadPost } from '../api/fn/documents/upload-document-api-documents-upload-post';
import { deleteDocumentApiDocumentsDocumentIdDelete } from '../api/fn/documents/delete-document-api-documents-document-id-delete';
import { DocumentResponse } from '../api/models/document-response';

@Injectable({
  providedIn: 'root',
})
export class DocumentService {
  constructor(private api: Api) {}

  getDocuments(): Promise<DocumentResponse[]> {
    return this.api.invoke(readDocumentsApiDocumentsGet, { limit: 500 });
  }

  uploadDocument(params: { file?: File | null; url?: string | null; category_id?: string | null }): Promise<DocumentResponse> {
    return this.api.invoke(uploadDocumentApiDocumentsUploadPost, {
      body: {
        file: params.file as any,
        url: params.url ?? null,
        category_id: params.category_id as any,
      },
    });
  }

  deleteDocument(document_id: string): Promise<void> {
    return this.api.invoke(deleteDocumentApiDocumentsDocumentIdDelete, { document_id: document_id as any });
  }
}
