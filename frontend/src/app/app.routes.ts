import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'review-hub', pathMatch: 'full' },
  { 
    path: 'review-hub', 
    loadComponent: () => import('./features/review-hub/pages/review-dashboard/review-dashboard.component').then(m => m.ReviewDashboardComponent)
  },
  { 
    path: 'taxonomy', 
    loadComponent: () => import('./features/taxonomy/pages/category-manager/category-manager.component').then(m => m.CategoryManagerComponent)
  },
  { 
    path: 'knowledge-base', 
    loadComponent: () => import('./features/knowledge-base/pages/document-manager/document-manager.component').then(m => m.DocumentManagerComponent)
  }
];
