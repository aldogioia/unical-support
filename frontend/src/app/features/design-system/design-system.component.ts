import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { DsIconComponent } from './ds-icon.component';
import { DsPlaygroundComponent } from './ds-playground.component';

@Component({
  selector: 'app-design-system', standalone: true,
  imports: [DsIconComponent, DsPlaygroundComponent],
  templateUrl: './design-system.component.html', styleUrls: ['./ds-tokens.css', './design-system.component.css', './ds-identity.css', './ds-foundations.css', './ds-preferences.css', './ds-layout-responsive.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.ds-high-contrast]': 'highContrast()', '[class.ds-comfortable]': 'comfortable()', '[class.ds-reduce-motion]': 'reduceMotion()' }
})
export class DesignSystemComponent {
  private readonly destroyRef = inject(DestroyRef);
  readonly content = viewChild.required<ElementRef<HTMLElement>>('content');
  readonly preferences = viewChild.required<ElementRef<HTMLDialogElement>>('preferences');
  readonly search = signal('');
  readonly activeSection = signal('foundations');
  readonly highContrast = signal(false);
  readonly comfortable = signal(false);
  readonly reduceMotion = signal(false);
  readonly copied = signal('');
  private copyTimer?: ReturnType<typeof setTimeout>;
  readonly sections = [
    { id: 'foundations', number: '01', label: 'Foundations', icon: 'palette', description: 'Logo, colori e tipografia' },
    { id: 'buttons', number: '02', label: 'Buttons & Actions', icon: 'cursor', description: 'Varianti, dimensioni e stati' },
    { id: 'forms', number: '03', label: 'Form Controls', icon: 'sliders', description: 'Input, editor e selezioni' },
    { id: 'data', number: '04', label: 'Data & AI Workflow', icon: 'mail', description: 'Email, badge e fonti AI' },
    { id: 'feedback', number: '05', label: 'Feedback & Navigation', icon: 'layers', description: 'Overlay, avvisi e navigazione' }
  ];
  readonly filteredSections = computed(() => this.sections.filter(s => `${s.label} ${s.description}`.toLowerCase().includes(this.search().toLowerCase())));
  readonly brand = [
    { name: 'Primary · Rosso Unical', token: '--ds-color-primary', hex: '#B61918', description: 'L’azione principale, sempre riconoscibile.', shades: ['#FFF5F4', '#FDE8E7', '#F9CECC', '#F1A4A1', '#E56B65', '#D33D35', '#B61918', '#981513', '#7C1715', '#651916'] },
    { name: 'Secondary · Grigio del logo', token: '--ds-color-secondary', hex: '#9E9E9D', description: 'Un riferimento neutro per superfici e dettagli.', shades: ['#FAFAFA', '#F4F4F4', '#E7E7E7', '#D4D4D3', '#B8B8B7', '#9E9E9D', '#737372', '#535352', '#3A3A39', '#242423'] },
    { name: 'Accent · Nero del logo', token: '--ds-color-accent', hex: '#000000', description: 'Gerarchia, precisione e massima leggibilità.', shades: ['#F8F8F8', '#EFEFEF', '#DCDCDC', '#BDBDBD', '#959595', '#727272', '#555555', '#383838', '#1B1B1B', '#000000'] }
  ];
  readonly shadeLabels = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900'];
  readonly neutrals = [
    { name: 'Background', token: '--ds-bg', hex: '#F7F8FA' },
    { name: 'Surface', token: '--ds-surface', hex: '#FFFFFF' },
    { name: 'Surface elevated', token: '--ds-elevated', hex: '#FFFFFF' },
    { name: 'Border', token: '--ds-border', hex: '#E2E5EA' },
    { name: 'Text primary', token: '--ds-text', hex: '#20242C' },
    { name: 'Text secondary', token: '--ds-text-secondary', hex: '#535C6B' },
    { name: 'Text muted', token: '--ds-text-muted', hex: '#667080' }
  ];
  readonly semantics = [
    { name: 'Success', use: 'Approved & Sent', token: '--ds-success', hex: '#197149', soft: '#EDF8F1', icon: 'check' },
    { name: 'Warning', use: 'Pending Review / Bozza', token: '--ds-warning', hex: '#946200', soft: '#FFF8E6', icon: 'clock' },
    { name: 'Danger', use: 'Escalated / Errore', token: '--ds-danger', hex: '#B42332', soft: '#FFF0F1', icon: 'warning' },
    { name: 'Info · AI', use: 'Agent Active / Retrieval', token: '--ds-info', hex: '#6352B9', soft: '#F2EFFE', icon: 'sparkle' }
  ];
  readonly typeSamples = [
    { name: 'H1', size: '36 / 44 · 650', css: 'type-h1', token: '--ds-type-h1', text: 'Ogni risposta, più chiara.' },
    { name: 'H2', size: '24 / 32 · 650', css: 'type-h2', token: '--ds-type-h2', text: 'Il lavoro, in ordine.' },
    { name: 'H3', size: '18 / 26 · 600', css: 'type-h3', token: '--ds-type-h3', text: 'Una segreteria più connessa' },
    { name: 'H4', size: '15 / 22 · 600', css: 'type-h4', token: '--ds-type-h4', text: 'Dettagli della conversazione' },
    { name: 'Body large', size: '16 / 26 · 400', css: 'type-large', token: '--ds-type-large', text: 'Più contesto, decisioni migliori.' },
    { name: 'Body regular', size: '14 / 22 · 400', css: 'type-regular', token: '--ds-type-regular', text: 'Rivedi la bozza prima di inviare la risposta allo studente.' },
    { name: 'Caption', size: '12 / 18 · 400', css: 'type-caption', token: '--ds-type-caption', text: 'Ultimo aggiornamento · 2 minuti fa' },
    { name: 'Monospace', size: '12 / 20 · 400', css: 'type-mono', token: '--ds-type-mono', text: 'thread_8f2a · confidence: 0.96 · tokens: 1248' }
  ];
  readonly spacing = [4, 8, 12, 16, 24, 32, 48, 64];
  readonly radii = [{ name: 'sm', value: '4px' }, { name: 'md', value: '8px' }, { name: 'lg', value: '12px' }, { name: 'full', value: '999px' }];

  constructor() { this.destroyRef.onDestroy(() => clearTimeout(this.copyTimer)); }

  updateActiveSection(): void {
    const root = this.content().nativeElement;
    const boundary = root.getBoundingClientRect().top + 160;
    const sections = Array.from(root.querySelectorAll<HTMLElement>('section[id]'));
    const current = sections.filter(section => section.getBoundingClientRect().top <= boundary).pop();
    if (current) this.activeSection.set(current.id);
  }

  navigate(event: Event, id: string): void {
    event.preventDefault();
    const section = this.content().nativeElement.querySelector<HTMLElement>(`#${id}`);
    section?.scrollIntoView({ behavior: this.reduceMotion() || window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
    section?.focus({ preventScroll: true });
    this.activeSection.set(id);
  }

  async copy(hex: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(hex);
      this.copied.set(`${hex} copiato negli appunti`);
    } catch { this.copied.set(`Copia manualmente: ${hex}`); }
    clearTimeout(this.copyTimer);
    this.copyTimer = setTimeout(() => this.copied.set(''), 2500);
  }

  openPreferences(): void { this.preferences().nativeElement.showModal(); }
  closePreferencesOnBackdrop(event: MouseEvent): void { if (event.target === event.currentTarget) this.closePreferences(); }
  closePreferences(): void { this.preferences().nativeElement.close(); }
  resetPreferences(): void { this.highContrast.set(false); this.comfortable.set(false); this.reduceMotion.set(false); }
}
