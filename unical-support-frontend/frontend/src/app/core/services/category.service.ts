import { Injectable } from '@angular/core';
import { Api } from '../api/api';
import { readCategoriesApiCategoriesGet } from '../api/fn/categories/read-categories-api-categories-get';
import { createCategoryApiCategoriesPost } from '../api/fn/categories/create-category-api-categories-post';
import { updateCategoryApiCategoriesCategoryIdPut } from '../api/fn/categories/update-category-api-categories-category-id-put';
import { deleteCategoryApiCategoriesCategoryIdDelete } from '../api/fn/categories/delete-category-api-categories-category-id-delete';
import { CategoryResponse } from '../api/models/category-response';
import { CategoryCreate } from '../api/models/category-create';
import { CategoryUpdate } from '../api/models/category-update';

@Injectable({
  providedIn: 'root',
})
export class CategoryService {
  private cache: CategoryResponse[] | null = null;

  constructor(private api: Api) {}

  async getCategories(forceRefresh: boolean = false): Promise<CategoryResponse[]> {
    if (!forceRefresh && this.cache !== null) {
      return this.cache;
    }

    const categories = await this.api.invoke(readCategoriesApiCategoriesGet, { limit: 500 });
    this.cache = categories;
    return categories;
  }

  async createCategory(body: CategoryCreate): Promise<CategoryResponse> {
    const category = await this.api.invoke(createCategoryApiCategoriesPost, { body });
    this.cache = null;
    return category;
  }

  async updateCategory(category_id: string, body: CategoryUpdate): Promise<CategoryResponse> {
    const category = await this.api.invoke(updateCategoryApiCategoriesCategoryIdPut, {
      category_id: category_id as any,
      body,
    });
    this.cache = null;
    return category;
  }

  async deleteCategory(category_id: string): Promise<void> {
    await this.api.invoke(deleteCategoryApiCategoriesCategoryIdDelete, { category_id: category_id as any });
    this.cache = null;
  }
}
