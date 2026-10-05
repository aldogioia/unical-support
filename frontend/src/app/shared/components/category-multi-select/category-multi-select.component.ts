import {
  Component, ChangeDetectionStrategy, ElementRef, EventEmitter, HostListener,
  Input, OnInit, Output, computed, inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CategoryResponse } from '../../../core/api/models/category-response';

/**
 * Selettore multiplo di categorie (dropdown con checkbox e ricerca).
 * Uso: <app-category-multi-select [categories]="..." [(selectedIds)]="ids" />
 */
@Component({
  selector: 'app-category-multi-select',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './category-multi-select.component.html',
  styleUrl: './category-multi-select.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CategoryMultiSelectComponent implements OnInit {
  private host = inject(ElementRef<HTMLElement>);

  private _categories = signal<CategoryResponse[]>([]);
  private _selected = signal<string[]>([]);

  @Input() set categories(value: CategoryResponse[] | null | undefined) {
    this._categories.set(value ?? []);
  }
  @Input() set selectedIds(value: string[] | null | undefined) {
    this._selected.set([...(value ?? [])]);
  }
  @Input() disabled = false;
  @Input() placeholder = 'Nessuna categoria';
  @Input() startOpen = false;

  @Output() selectedIdsChange = new EventEmitter<string[]>();

  open = signal(false);
  private openedAt = 0;
  search = signal('');

  selectedSet = computed(() => new Set(this._selected()));

  selectedCategories = computed(() => {
    const set = this.selectedSet();
    return this._categories().filter(c => set.has(c.id));
  });

  filteredCategories = computed(() => {
    const q = this.search().trim().toLowerCase();
    const all = this._categories();
    return q ? all.filter(c => c.name.toLowerCase().includes(q)) : all;
  });

  ngOnInit() {
    if (this.startOpen && !this.disabled) {
      this.openedAt = performance.now();
      this.open.set(true);
    }
  }

  toggleOpen() {
    if (this.disabled) return;
    this.open.update(v => !v);
    if (!this.open()) this.search.set('');
  }

  isSelected(id: string): boolean {
    return this.selectedSet().has(id);
  }

  toggle(id: string) {
    if (this.disabled) return;
    const current = this._selected();
    const next = current.includes(id) ? current.filter(x => x !== id) : [...current, id];
    this._selected.set(next);
    this.selectedIdsChange.emit(next);
  }

  remove(id: string, event: Event) {
    event.stopPropagation();
    this.toggle(id);
  }

  clear() {
    this._selected.set([]);
    this.selectedIdsChange.emit([]);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    // Ignora il click che ha causato l'apertura automatica (startOpen)
    if (event.timeStamp <= this.openedAt) return;
    if (this.open() && !this.host.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
      this.search.set('');
    }
  }

  @HostListener('keydown.escape')
  onEscape() {
    this.open.set(false);
  }
}
