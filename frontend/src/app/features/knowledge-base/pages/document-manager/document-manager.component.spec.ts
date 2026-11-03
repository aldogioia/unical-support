import { signal } from '@angular/core';
import { TestBed, fakeAsync, flushMicrotasks, tick } from '@angular/core/testing';
import { Api } from '../../../../core/api/api';
import { readCategoriesApiCategoriesGet } from '../../../../core/api/fn/categories/read-categories-api-categories-get';
import { updateDocumentApiDocumentsDocumentIdPut } from '../../../../core/api/fn/documents/update-document-api-documents-document-id-put';
import { uploadDocumentApiDocumentsUploadPost } from '../../../../core/api/fn/documents/upload-document-api-documents-upload-post';
import { forceIndexDocumentApiDocumentsDocumentIdForceIndexPost } from '../../../../core/api/fn/documents/force-index-document-api-documents-document-id-force-index-post';
import { readDocumentsApiDocumentsGet } from '../../../../core/api/fn/documents/read-documents-api-documents-get';
import { UserResponse } from '../../../../core/api/models/user-response';
import { AuthService } from '../../../../core/services/auth.service';
import {
  DocumentManagerComponent,
  FORCED_REVIEW_NOTE,
  parseReviewNotes,
  withKnownType,
} from './document-manager.component';

const category = {
  id: 'category-1',
  name: 'Tasse',
  description: 'Contributi e ISEE',
};
const source = {
  id: 'document-1',
  filename: 'guida.pdf',
  content_type: 'application/pdf',
  extracted_text: 'Testo completo sui contributi',
  reference_url: 'https://www.unical.it/guida.pdf',
  categories: [category],
};
const currentUser = signal<UserResponse | null>(null);
describe('Knowledge base master-detail', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(async () => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.callFake(((operation: unknown) =>
      Promise.resolve(
        operation === readCategoriesApiCategoriesGet ? [category] : [source],
      )) as any);
    await TestBed.configureTestingModule({
      imports: [DocumentManagerComponent],
      providers: [
        { provide: Api, useValue: api },
        { provide: AuthService, useValue: { currentUser } },
      ],
    }).compileComponents();
  });
  it('keeps upload controls out of the initial list and opens them only when creating', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.upload-zone')).toBeNull();
    component.openCreate();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.upload-zone')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.source-tabs')).toBeNull();
    expect(
      fixture.nativeElement.querySelectorAll('input[type="url"]').length,
    ).toBe(0);
    component.handleFiles([new File(['x'], 'guida.txt', { type: 'text/plain' })]);
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelectorAll('input[type="url"]').length,
    ).toBe(1);
    expect(fixture.nativeElement.textContent).not.toContain(
      'Importa pagina web',
    );
    fixture.destroy();
  }));
  it('filters name, content, URL and categories without another API request', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    const count = api.invoke.calls.count();
    for (const query of ['guida', 'completo', 'unical.it', 'tasse']) {
      component.search.set(query);
      expect(component.filteredDocuments().length).toBe(1);
    }
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-workspace-header select')).toBeNull();
    component.search.set('missing');
    expect(component.filteredDocuments().length).toBe(0);
    expect(api.invoke.calls.count()).toBe(count);
    fixture.destroy();
  }));
  it('updates document categories and source link and keeps its detail visible', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectDocument(source);
    component.startEditCategories(source);
    component.editingCategoryIds = [];
    api.invoke.and.returnValue(
      Promise.resolve({ ...source, categories: [] }) as any,
    );
    component.saveDocumentCategories(source);
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(
      updateDocumentApiDocumentsDocumentIdPut,
      {
        document_id: source.id,
        body: { category_ids: [], reference_url: source.reference_url },
      },
    );
    expect(component.selectedDocument()?.categories).toEqual([]);
    fixture.destroy();
  }));
  it('queues chosen files and uploads only after Invia, with that file\'s link and categories', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.openCreate();
    api.invoke.and.returnValue(
      Promise.resolve({ ...source, id: 'document-2' }) as any,
    );
    const file = new File(['Testo'], 'guida.txt', { type: 'text/plain' });
    component.handleFiles([file]);
    fixture.detectChanges();
    expect(api.invoke).not.toHaveBeenCalledWith(uploadDocumentApiDocumentsUploadPost, jasmine.anything());
    expect(fixture.nativeElement.querySelector('.upload-zone')).toBeNull();
    expect(fixture.nativeElement.querySelector('.queue-send').textContent).toContain('Invia 1/1');
    component.referenceUrl = 'https://www.unical.it/guida.pdf';
    component.selectedCategoryIds = ['category-1'];
    component.sendCurrentFile();
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(
      uploadDocumentApiDocumentsUploadPost,
      {
        body: {
          file: file as any,
          reference_url: 'https://www.unical.it/guida.pdf',
          category_ids: ['category-1'],
        },
      },
    );
    expect(component.documents().length).toBe(2);
    expect(component.uploading()).toBeFalse();
    expect(component.pendingFiles().length).toBe(0);
    expect(component.uploadNotice()).toContain('Documento inviato');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.upload-zone')).not.toBeNull();
    fixture.destroy();
  }));
  it('allows clearing a source link without re-uploading the file', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectDocument(source);
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('#document-reference-url').value,
    ).toBe(source.reference_url);
    component.editingReferenceUrl = '';
    api.invoke.and.returnValue(
      Promise.resolve({ ...source, reference_url: null }) as any,
    );
    component.saveDocumentCategories(source);
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(
      updateDocumentApiDocumentsDocumentIdPut,
      {
        document_id: source.id,
        body: { category_ids: ['category-1'], reference_url: null },
      },
    );
    expect(component.selectedDocument()?.reference_url).toBeNull();
    expect(component.editNotice()).toBe('Modifiche salvate.');
    fixture.destroy();
  }));
  it('blocks invalid source links before submitting an update', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.selectDocument(source);
    const count = api.invoke.calls.count();
    component.editingReferenceUrl = 'javascript:alert(1)';
    component.saveDocumentCategories(source);
    flushMicrotasks();
    expect(api.invoke.calls.count()).toBe(count);
    expect(component.editError()).toContain('URL valido');
    fixture.destroy();
  }));
});

const reviewed = {
  ...source,
  id: 'document-review',
  filename: 'Regolamento Tasse.pdf',
  processing_status: 'needs_review',
  review_notes:
    "Parte 1/2: dati persi: 14, 15\nParte 2/2: dati persi: 2024; dati non presenti nell'originale: 31/08",
  extracted_text:
    'ATTENZIONE: verifica di fedeltà numerica/fattuale fallita, documento NON indicizzato.\n\nTesto generato',
};
describe('Document review for administrators', () => {
  let api: jasmine.SpyObj<Api>;
  let listed: any[];
  beforeEach(async () => {
    listed = [reviewed];
    currentUser.set({ id: 'u1', email: 'admin@unical.it', is_active: true, role: 'admin' });
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.callFake(((operation: unknown) => {
      if (operation === readCategoriesApiCategoriesGet) return Promise.resolve([category]);
      if (operation === forceIndexDocumentApiDocumentsDocumentIdForceIndexPost)
        return Promise.resolve({ ...reviewed, processing_status: 'pending' });
      return Promise.resolve(listed);
    }) as any);
    await TestBed.configureTestingModule({
      imports: [DocumentManagerComponent],
      providers: [
        { provide: Api, useValue: api },
        { provide: AuthService, useValue: { currentUser } },
      ],
    }).compileComponents();
  });
  afterEach(() => currentUser.set(null));

  function open() {
    const fixture = TestBed.createComponent(DocumentManagerComponent);
    fixture.detectChanges();
    flushMicrotasks();
    fixture.componentInstance.selectDocument(reviewed as any);
    fixture.detectChanges();
    return fixture;
  }

  it('parses lost and added data for every part of the review notes', () => {
    const parts = parseReviewNotes(FORCED_REVIEW_NOTE + '\n' + reviewed.review_notes);
    expect(parts.map((p) => p.label)).toEqual(['Parte 1 di 2', 'Parte 2 di 2']);
    expect(parts[0].lost).toEqual(['14', '15']);
    expect(parts[1].lost).toEqual(['2024']);
    expect(parts[1].extra).toEqual(['31/08']);
  });

  it('marks documents to review in the list', fakeAsync(() => {
    const fixture = open();
    expect(fixture.nativeElement.querySelector('.review-badge').textContent).toContain('Da verificare');
    fixture.destroy();
  }));

  it('shows the review section with the differences and a risk warning to admins', fakeAsync(() => {
    const fixture = open();
    const section = fixture.nativeElement.querySelector('.review-section');
    expect(section).not.toBeNull();
    expect(section.querySelectorAll('.review-part').length).toBe(2);
    expect(section.querySelector('.review-chip-extra').textContent).toContain('31/08');
    expect(section.querySelector('.review-risk')).not.toBeNull();
    expect(section.querySelector('.review-force')).not.toBeNull();
    fixture.destroy();
  }));

  it('hides the review section from non-admin users', fakeAsync(() => {
    currentUser.set({ id: 'u2', email: 'op@unical.it', is_active: true, role: 'user' });
    const fixture = open();
    expect(fixture.nativeElement.querySelector('.review-section')).toBeNull();
    fixture.destroy();
  }));

  it('asks for confirmation, forces indexing and follows it until it is indexed', fakeAsync(() => {
    const fixture = open(),
      component = fixture.componentInstance;
    fixture.nativeElement.querySelector('.review-force').click();
    fixture.detectChanges();
    expect(api.invoke).not.toHaveBeenCalledWith(
      forceIndexDocumentApiDocumentsDocumentIdForceIndexPost,
      jasmine.anything(),
    );
    expect(fixture.nativeElement.querySelector('.review-confirm')).not.toBeNull();
    component.forceIndex(reviewed as any);
    flushMicrotasks();
    fixture.detectChanges();
    expect(api.invoke).toHaveBeenCalledWith(
      forceIndexDocumentApiDocumentsDocumentIdForceIndexPost,
      { document_id: reviewed.id },
    );
    expect(fixture.nativeElement.querySelector('.review-progress')).not.toBeNull();
    listed = [{ ...reviewed, processing_status: 'indexed', extracted_text: 'Testo generato',
      review_notes: FORCED_REVIEW_NOTE + '\n' + reviewed.review_notes }];
    tick(3000);
    flushMicrotasks();
    fixture.detectChanges();
    expect(component.isForcing(reviewed as any)).toBeFalse();
    expect(component.reviewNotice()).toContain('è stato indicizzato');
    expect(fixture.nativeElement.querySelector('.review-section')).toBeNull();
    expect(fixture.nativeElement.querySelector('.review-forced')).not.toBeNull();
    expect(api.invoke).toHaveBeenCalledWith(readDocumentsApiDocumentsGet, {});
    fixture.destroy();
  }));

  it('reports a failed start without leaving the document stuck', fakeAsync(() => {
    const fixture = open(),
      component = fixture.componentInstance;
    api.invoke.and.returnValue(Promise.reject(new Error('409')) as any);
    component.forceIndex(reviewed as any);
    flushMicrotasks();
    expect(component.isForcing(reviewed as any)).toBeFalse();
    expect(component.reviewError()).toContain("Impossibile avviare");
    fixture.destroy();
  }));
});

describe('Upload queue: one file at a time', () => {
  let api: jasmine.SpyObj<Api>;
  let uploads: any[];
  beforeEach(async () => {
    uploads = [];
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.callFake(((operation: unknown, params: any) => {
      if (operation === readCategoriesApiCategoriesGet) return Promise.resolve([category]);
      if (operation === uploadDocumentApiDocumentsUploadPost) {
        uploads.push(params.body);
        return Promise.resolve({ ...source, id: 'new-' + uploads.length, filename: params.body.file.name });
      }
      return Promise.resolve([source]);
    }) as any);
    await TestBed.configureTestingModule({
      imports: [DocumentManagerComponent],
      providers: [
        { provide: Api, useValue: api },
        { provide: AuthService, useValue: { currentUser } },
      ],
    }).compileComponents();
  });

  function start(...names: string[]) {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.openCreate();
    component.handleFiles(names.map((n) => new File(['x'], n, { type: 'text/plain' })));
    fixture.detectChanges();
    return { fixture, component };
  }

  it('walks through the queue with Invia 1/3, 2/3, 3/3 and empty fields for every file', fakeAsync(() => {
    const { fixture, component } = start('a.txt', 'b.txt', 'c.txt');
    const button = () => fixture.nativeElement.querySelector('.queue-send').textContent;
    expect(button()).toContain('Invia 1/3');
    expect(fixture.nativeElement.querySelector('.queue-file').textContent).toContain('a.txt');
    component.referenceUrl = 'https://www.unical.it/a';
    component.selectedCategoryIds = ['category-1'];
    component.sendCurrentFile();
    flushMicrotasks();
    fixture.detectChanges();
    expect(button()).toContain('Invia 2/3');
    expect(component.referenceUrl).toBe('');
    expect(component.selectedCategoryIds).toEqual([]);
    component.referenceUrl = 'https://www.unical.it/b';
    component.sendCurrentFile();
    flushMicrotasks();
    fixture.detectChanges();
    expect(button()).toContain('Invia 3/3');
    component.sendCurrentFile();
    flushMicrotasks();
    fixture.detectChanges();
    expect(uploads.map((u) => [u.file.name, u.reference_url, u.category_ids])).toEqual([
      ['a.txt', 'https://www.unical.it/a', ['category-1']],
      ['b.txt', 'https://www.unical.it/b', []],
      ['c.txt', null, []],
    ]);
    expect(component.uploadNotice()).toContain('3 documenti inviati');
    expect(fixture.nativeElement.querySelector('.upload-zone')).not.toBeNull();
    fixture.destroy();
  }));

  it('skips a file without uploading it and keeps the position', fakeAsync(() => {
    const { fixture, component } = start('a.txt', 'b.txt');
    component.skipCurrentFile();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.queue-send').textContent).toContain('Invia 2/2');
    component.sendCurrentFile();
    flushMicrotasks();
    expect(uploads.map((u) => u.file.name)).toEqual(['b.txt']);
    expect(component.uploadNotice()).toContain('Documento inviato');
    fixture.destroy();
  }));

  it('stays on the same file when the upload fails', fakeAsync(() => {
    const { component } = start('a.txt', 'b.txt');
    api.invoke.and.returnValue(Promise.reject(new Error('rete')) as any);
    component.sendCurrentFile();
    flushMicrotasks();
    expect(component.currentFile()?.name).toBe('a.txt');
    expect(component.pendingFiles().length).toBe(2);
    expect(component.uploadError()).toContain('a.txt');
    expect(component.uploading()).toBeFalse();
  }));

  it('discards files with formats that are not accepted', fakeAsync(() => {
    const { component } = start('a.txt', 'setup.exe');
    expect(component.pendingFiles().map((f) => f.name)).toEqual(['a.txt']);
    expect(component.uploadError()).toContain('scartato');
  }));

  it('asks before closing with files still in the queue', fakeAsync(() => {
    const { component } = start('a.txt', 'b.txt');
    spyOn(window, 'confirm').and.returnValue(false);
    component.closeDetail();
    expect(window.confirm).toHaveBeenCalled();
    expect(component.creating()).toBeTrue();
    expect(component.pendingFiles().length).toBe(2);
    (window.confirm as jasmine.Spy).and.returnValue(true);
    component.closeDetail();
    expect(component.creating()).toBeFalse();
    expect(component.pendingFiles().length).toBe(0);
  }));

  it('sends markdown as text/markdown when the browser does not know the type (Firefox)', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.openCreate();
    component.handleFiles([new File(['# Titolo'], 'guida.md', { type: 'application/octet-stream' })]);
    component.sendCurrentFile();
    flushMicrotasks();
    expect(uploads[0].file.type).toBe('text/markdown');
    expect(uploads[0].file.name).toBe('guida.md');
    expect(withKnownType(new File(['x'], 'a.pdf', { type: 'application/pdf' })).type).toBe('application/pdf');
    expect(withKnownType(new File(['x'], 'b.md', { type: '' })).type).toBe('text/markdown');
    fixture.destroy();
  }));
});
