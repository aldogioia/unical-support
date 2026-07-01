import { Component, OnInit, ChangeDetectionStrategy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../../core/api/api';
import { readCategoriesApiCategoriesGet } from '../../../../core/api/fn/categories/read-categories-api-categories-get';
import { createCategoryApiCategoriesPost } from '../../../../core/api/fn/categories/create-category-api-categories-post';
import { updateCategoryApiCategoriesCategoryIdPut } from '../../../../core/api/fn/categories/update-category-api-categories-category-id-put';
import { deleteCategoryApiCategoriesCategoryIdDelete } from '../../../../core/api/fn/categories/delete-category-api-categories-category-id-delete';
import { CategoryResponse } from '../../../../core/api/models/category-response';

@Component({
  selector: 'app-category-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './category-manager.component.html',
  styleUrl: './category-manager.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CategoryManagerComponent implements OnInit {
  private api = inject(Api);
  
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
    if (!this.newCategory.name) return;
    try {
      const created = await this.api.invoke(createCategoryApiCategoriesPost, {
        body: { name: this.newCategory.name, description: this.newCategory.description }
      });
      this.categories.update(cats => [created, ...cats]);
      this.cancelAdd();
    } catch (e) {
      console.error(e);
    }
  }

  cancelAdd() {
    this.isAdding.set(false);
    this.newCategory = { name: '', description: '' };
  }

  startEdit(cat: CategoryResponse) {
    this.editingId.set(cat.id);
    this.editCategory = { name: cat.name, description: cat.description || '' };
  }

  cancelEdit() {
    this.editingId.set(null);
  }

  async saveEdit(id: string) {
    try {
      const updated = await this.api.invoke(updateCategoryApiCategoriesCategoryIdPut, {
        category_id: id as any,
        body: { name: this.editCategory.name, description: this.editCategory.description }
      });
      this.categories.update(cats => cats.map(c => c.id === id ? updated : c));
      this.cancelEdit();
    } catch (e) {
      console.error(e);
    }
  }

  async deleteCategory(id: string) {
    if (!confirm('Are you sure you want to delete this category?')) return;
    try {
      await this.api.invoke(deleteCategoryApiCategoriesCategoryIdDelete, { category_id: id as any });
      this.categories.update(cats => cats.filter(c => c.id !== id));
    } catch (e) {
      console.error(e);
    }
  }
}
