import { Routes } from '@angular/router';
import { ClassificationPageComponent } from './pages/classification-page/classification-page.component';
import { AnswersPageComponent } from './pages/answers-page/answers-page.component';
import { TemplatePageComponent } from './pages/template-page/template-page.component';
import { DocumentPageComponent } from './pages/document-page/document-page.component';

export const routes: Routes = [
  { path: '', redirectTo: 'classifications', pathMatch: 'full' },
  { path: 'classifications', component: ClassificationPageComponent },
  { path: 'answers', component: AnswersPageComponent },
  { path: 'templates', component: TemplatePageComponent },
  { path: 'documents', component: DocumentPageComponent },
];
