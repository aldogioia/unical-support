import { TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { Api } from '../../../../core/api/api';
import { readCategoriesApiCategoriesGet } from '../../../../core/api/fn/categories/read-categories-api-categories-get';
import { updateDocumentApiDocumentsDocumentIdPut } from '../../../../core/api/fn/documents/update-document-api-documents-document-id-put';
import { uploadDocumentApiDocumentsUploadPost } from '../../../../core/api/fn/documents/upload-document-api-documents-upload-post';
import { DocumentManagerComponent } from './document-manager.component';

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
      providers: [{ provide: Api, useValue: api }],
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
    component.categoryFilter.set('missing');
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
  it('uploads only a local file with its optional source link and categories', fakeAsync(() => {
    const fixture = TestBed.createComponent(DocumentManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.openCreate();
    component.referenceUrl = 'https://www.unical.it/guida.pdf';
    component.selectedCategoryIds = ['category-1'];
    api.invoke.and.returnValue(
      Promise.resolve({ ...source, id: 'document-2' }) as any,
    );
    const file = new File(['Testo'], 'guida.txt', { type: 'text/plain' });
    component.handleFiles([file] as unknown as FileList);
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
