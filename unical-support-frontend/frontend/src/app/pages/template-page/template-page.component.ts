import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import { FileAddIcon, FileEditIcon, NoteIcon, CheckmarkCircle01Icon, Cancel01Icon } from '@hugeicons/core-free-icons';
import { CategoryService } from '../../core/services/category.service';
import { TemplateService } from '../../core/services/template.service';
import { CategoryResponse } from '../../core/api/models/category-response';
import { TemplateResponse } from '../../core/api/models/template-response';
import { TemplateStatusFormatPipe } from '../../shared/pipes/template-status-format.pipe';

const PARAMETER_REGEX = /\[([A-Za-z0-9_]+)\]/g;

@Component({
  selector: 'app-template-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, HugeiconsIconComponent, TemplateStatusFormatPipe],
  templateUrl: './template-page.component.html',
  styleUrls: [
    './template-page.component.css',
    '../../../../public/styles/layout.css',
    '../../../../public/styles/input.css',
  ],
})
export class TemplatePageComponent implements OnInit {
  protected readonly NoteIcon = NoteIcon;
  protected readonly FileEditIcon = FileEditIcon;
  protected readonly FileAddIcon = FileAddIcon;
  protected readonly CheckmarkCircle01Icon = CheckmarkCircle01Icon;
  protected readonly Cancel01Icon = Cancel01Icon;

  protected templates: TemplateResponse[] = [];
  protected categories: CategoryResponse[] = [];
  protected skeletons: number[] = Array(5).fill(0);

  protected selectedTemplate: TemplateResponse | null = null;
  protected isFetching = false;
  protected isLoading = false;
  protected showOnlyPending = false;

  protected form: FormGroup;
  protected detectedParameters: string[] = [];

  constructor(
    private formBuilder: FormBuilder,
    private changeDetector: ChangeDetectorRef,
    private categoryService: CategoryService,
    private templateService: TemplateService,
  ) {
    this.form = this.formBuilder.group({
      id: [null],
      name: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(100)]],
      subject_template: ['', [Validators.maxLength(255)]],
      body_template: ['', [Validators.required, Validators.minLength(10)]],
      categoryIds: this.formBuilder.array([]),
    });
  }

  get filteredTemplates(): TemplateResponse[] {
    return this.showOnlyPending
      ? this.templates.filter(t => t.status === 'PENDING_APPROVAL')
      : this.templates;
  }

  get categoryIds(): FormArray {
    return this.form.get('categoryIds') as FormArray;
  }

  ngOnInit(): void {
    this.isFetching = true;

    this.categoryService.getCategories().then(categories => (this.categories = categories));

    this.loadTemplates();

    this.form.get('body_template')?.valueChanges.subscribe((content: string) => {
      this.detectedParameters = this.parseParameters(content);
    });
    this.form.get('subject_template')?.valueChanges.subscribe(() => {
      this.detectedParameters = this.parseParameters(this.form.get('body_template')?.value ?? '');
    });
  }

  private loadTemplates() {
    this.isFetching = true;
    this.templateService.getTemplates().then(
      templates => {
        this.templates = templates;
        this.isFetching = false;
        this.changeDetector.detectChanges();
      },
      () => {
        this.isFetching = false;
        alert('Errore nel caricamento dei template');
      },
    );
  }

  isCategorySelected(categoryId: string): boolean {
    return this.categoryIds.value.includes(categoryId);
  }

  toggleCategory(categoryId: string, checked: boolean) {
    const current: string[] = this.categoryIds.value;
    if (checked && !current.includes(categoryId)) {
      this.categoryIds.push(this.formBuilder.control(categoryId));
    } else if (!checked) {
      const idx = current.indexOf(categoryId);
      if (idx >= 0) this.categoryIds.removeAt(idx);
    }
  }

  private parseParameters(content: string | null): string[] {
    if (!content) return [];
    const found = new Set<string>();
    let match;
    PARAMETER_REGEX.lastIndex = 0;
    while ((match = PARAMETER_REGEX.exec(content)) !== null) {
      found.add(match[1]);
    }
    return [...found];
  }

  selectTemplate(template: TemplateResponse): void {
    this.selectedTemplate = template;

    this.form.patchValue({
      id: template.id,
      name: template.name,
      subject_template: template.subject_template ?? '',
      body_template: template.body_template,
    }, { emitEvent: false });

    this.categoryIds.clear({ emitEvent: false });
    (template.categories ?? []).forEach(c => this.categoryIds.push(this.formBuilder.control(c.id), { emitEvent: false }));

    this.detectedParameters = this.parseParameters(template.body_template);
  }

  reset(): void {
    this.selectedTemplate = null;
    this.form.reset({
      id: null,
      name: '',
      subject_template: '',
      body_template: '',
    });
    this.categoryIds.clear();
    this.detectedParameters = [];
  }

  submit(): void {
    if (this.form.invalid || this.isLoading) return;
    this.isLoading = true;

    const formValue = this.form.value;
    const dto = {
      name: formValue.name,
      subject_template: formValue.subject_template || null,
      body_template: formValue.body_template,
      category_ids: formValue.categoryIds,
    };

    const request = this.selectedTemplate
      ? this.templateService.updateTemplate(this.selectedTemplate.id, dto)
      : this.templateService.createTemplate(dto as any);

    request.then(
      () => {
        this.isLoading = false;
        this.reset();
        this.loadTemplates();
        alert(this.selectedTemplate ? 'Template aggiornato con successo' : 'Template creato con successo');
      },
      (err) => {
        console.error(err);
        this.isLoading = false;
        alert("Errore durante il salvataggio del template");
      },
    );
  }

  deleteTemplate(): void {
    if (!this.selectedTemplate) return;

    if (confirm('Sei sicuro di voler eliminare questo template?')) {
      this.isLoading = true;

      this.templateService.deleteTemplate(this.selectedTemplate.id).then(
        () => {
          this.isLoading = false;
          this.reset();
          this.loadTemplates();
        },
        (err) => {
          console.error(err);
          this.isLoading = false;
          alert("Errore durante l'eliminazione");
        },
      );
    }
  }

  reviewTemplate(template: TemplateResponse, action: 'approve' | 'reject', event: Event): void {
    event.stopPropagation();
    this.templateService.reviewTemplate(template.id, action).then(
      () => {
        this.loadTemplates();
        if (this.selectedTemplate?.id === template.id) this.reset();
      },
      () => alert('Errore durante la revisione del template'),
    );
  }
}
