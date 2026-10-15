import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  signal,
  inject,
  computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DsIconComponent } from '../../../../shared/components/ds-icon/ds-icon.component';
import { WorkspaceHeaderComponent } from '../../../../shared/components/workspace-header/workspace-header.component';
import { DetailPanelDirective } from '../../../../shared/components/detail-panel.directive';
import { Api } from '../../../../core/api/api';
import { readCategoriesApiCategoriesGet } from '../../../../core/api/fn/categories/read-categories-api-categories-get';
import { createCategoryApiCategoriesPost } from '../../../../core/api/fn/categories/create-category-api-categories-post';
import { updateCategoryApiCategoriesCategoryIdPut } from '../../../../core/api/fn/categories/update-category-api-categories-category-id-put';
import { deleteCategoryApiCategoriesCategoryIdDelete } from '../../../../core/api/fn/categories/delete-category-api-categories-category-id-delete';
import { CategoryResponse } from '../../../../core/api/models/category-response';

@Component({
  selector: 'app-category-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    DsIconComponent,
    WorkspaceHeaderComponent,
    DetailPanelDirective,
  ],
  templateUrl: './category-manager.component.html',
  styleUrl: './category-manager.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CategoryManagerComponent implements OnInit {
  private api = inject(Api);
  readonly search = signal('');
  readonly saving = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly filteredCategories = computed(() => {
    const query = this.search().trim().toLocaleLowerCase('it');
    return this.categories().filter(
      (category) =>
        !query ||
        [category.name, category.description]
          .join(' ')
          .toLocaleLowerCase('it')
          .includes(query),
    );
  });
  readonly selectedCategory = computed(
    () =>
      this.categories().find((category) => category.id === this.editingId()) ??
      null,
  );
  openCreate(): void {
    if (this.saving()) return;
    this.cancelEdit();
    this.isAdding.set(true);
    this.error.set('');
    this.notice.set('');
  }
  closeDetail(): void {
    if (!this.saving()) {
      this.cancelAdd();
      this.cancelEdit();
      this.error.set('');
    }
  }

  categories = signal<CategoryResponse[]>([]);
  loading = signal<boolean>(true);
  isAdding = signal<boolean>(false);
  editingId = signal<string | null>(null);

  newCategory = { name: '', description: '' };
  editCategory = { name: '', description: '' };

  ngOnInit() {
    this.loadCategories();
  }

  async loadCategories() {
    this.loading.set(true);
    try {
      const data = await this.api.invoke(readCategoriesApiCategoriesGet, {});
      this.categories.set(data);
    } catch (e) {
      console.error(e);
    } finally {
      this.loading.set(false);
    }
  }

  async saveNewCategory() {
    if (!this.newCategory.name.trim() || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    try {
      const created = await this.api.invoke(createCategoryApiCategoriesPost, {
        body: {
          name: this.newCategory.name,
          description: this.newCategory.description,
        },
      });
      this.categories.update((cats) => [created, ...cats]);
      this.cancelAdd();
      this.notice.set('Categoria creata.');
    } catch (e) {
      this.error.set(
        'Impossibile creare la categoria. Verifica il nome e riprova.',
      );
      console.error(e);
    } finally {
      this.saving.set(false);
    }
  }

  cancelAdd() {
    this.isAdding.set(false);
    this.newCategory = { name: '', description: '' };
  }

  startEdit(cat: CategoryResponse) {
    if (this.saving()) return;
    this.cancelAdd();
    this.error.set('');
    this.notice.set('');
    this.editingId.set(cat.id);
    this.editCategory = { name: cat.name, description: cat.description || '' };
  }

  cancelEdit() {
    this.editingId.set(null);
  }

  async saveEdit(id: string) {
    if (this.saving() || !this.editCategory.name.trim()) return;
    this.saving.set(true);
    this.error.set('');
    try {
      const updated = await this.api.invoke(
        updateCategoryApiCategoriesCategoryIdPut,
        {
          category_id: id as any,
          body: {
            name: this.editCategory.name,
            description: this.editCategory.description,
          },
        },
      );
      this.categories.update((cats) =>
        cats.map((c) => (c.id === id ? updated : c)),
      );
      this.cancelEdit();
      this.notice.set('Categoria aggiornata.');
    } catch (e) {
      this.error.set('Impossibile salvare la categoria. Riprova.');
      console.error(e);
    } finally {
      this.saving.set(false);
    }
  }

  async deleteCategory(id: string) {
    if (
      !confirm(
        'Vuoi eliminare questa categoria? I documenti associati solo a questa categoria verranno eliminati.',
      )
    )
      return;
    try {
      await this.api.invoke(deleteCategoryApiCategoriesCategoryIdDelete, {
        category_id: id as any,
      });
      this.categories.update((cats) => cats.filter((c) => c.id !== id));
      if (this.editingId() === id) this.cancelEdit();
      this.notice.set('Categoria eliminata.');
    } catch (e) {
      console.error(e);
    }
  }
}
