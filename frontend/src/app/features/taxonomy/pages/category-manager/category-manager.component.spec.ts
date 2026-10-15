import { TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { Api } from '../../../../core/api/api';
import { createCategoryApiCategoriesPost } from '../../../../core/api/fn/categories/create-category-api-categories-post';
import { updateCategoryApiCategoriesCategoryIdPut } from '../../../../core/api/fn/categories/update-category-api-categories-category-id-put';
import { CategoryManagerComponent } from './category-manager.component';

const category = {
  id: 'category-1',
  name: 'Tirocini e Stage',
  description: 'Attivazione e crediti',
};
describe('Taxonomy master-detail', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(async () => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.returnValue(Promise.resolve([category]) as any);
    await TestBed.configureTestingModule({
      imports: [CategoryManagerComponent],
      providers: [{ provide: Api, useValue: api }],
    }).compileComponents();
  });
  it('selects a row for editing and switches to a separate creation form', fakeAsync(() => {
    const fixture = TestBed.createComponent(CategoryManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('.list-row').click();
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#category-name').value).toBe(
      category.name,
    );
    component.openCreate();
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(component.editingId()).toBeNull();
    expect(fixture.nativeElement.querySelector('#category-name').value).toBe(
      '',
    );
    component.search.set('crediti');
    expect(component.filteredCategories().length).toBe(1);
    component.search.set('inesistente');
    expect(component.filteredCategories().length).toBe(0);
    fixture.destroy();
  }));
  it('preserves the existing creation and edit API payloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(CategoryManagerComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.openCreate();
    component.newCategory = {
      name: 'Borse',
      description: 'Diritto allo studio',
    };
    api.invoke.and.returnValue(
      Promise.resolve({ id: 'new', ...component.newCategory }) as any,
    );
    component.saveNewCategory();
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(createCategoryApiCategoriesPost, {
      body: { name: 'Borse', description: 'Diritto allo studio' },
    });
    component.startEdit(category);
    component.editCategory = {
      name: category.name,
      description: 'Nuova descrizione',
    };
    api.invoke.and.returnValue(
      Promise.resolve({ ...category, description: 'Nuova descrizione' }) as any,
    );
    component.saveEdit(category.id);
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(
      updateCategoryApiCategoriesCategoryIdPut,
      {
        category_id: category.id,
        body: { name: category.name, description: 'Nuova descrizione' },
      },
    );
    fixture.destroy();
  }));
});
