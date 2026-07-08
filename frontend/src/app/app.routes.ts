import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/pages/login/login.component').then(m => m.LoginComponent)
  },
  { path: '', redirectTo: 'review-hub', pathMatch: 'full' },
  { 
    path: 'review-hub', 
    canActivate: [authGuard],
    loadComponent: () => import('./features/review-hub/pages/review-dashboard/review-dashboard.component').then(m => m.ReviewDashboardComponent)
  },
  { 
    path: 'taxonomy', 
    canActivate: [authGuard],
    loadComponent: () => import('./features/taxonomy/pages/category-manager/category-manager.component').then(m => m.CategoryManagerComponent)
  },
  { 
    path: 'knowledge-base', 
    canActivate: [authGuard],
    loadComponent: () => import('./features/knowledge-base/pages/document-manager/document-manager.component').then(m => m.DocumentManagerComponent)
  },
  {
    path: 'ai-settings',
    canActivate: [authGuard],
    loadComponent: () => import('./features/ai-settings/pages/model-settings/model-settings.component').then(m => m.ModelSettingsComponent)
  }
];
