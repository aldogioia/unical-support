import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { AiConfidenceComponent } from '../../shared/components/ai-confidence/ai-confidence.component';
import { AutoResizeDirective } from '../../shared/components/auto-resize.directive';
import { DsIconComponent } from './ds-icon.component';

type Tone = 'success' | 'warning' | 'danger' | 'info';

@Component({
  selector: 'ds-playground', standalone: true, imports: [DsIconComponent, AiConfidenceComponent, AutoResizeDirective],
  templateUrl: './ds-playground.component.html', styleUrls: ['./ds-controls.css', './ds-forms.css', './ds-upload-models.css', './ds-data.css', './ds-feedback.css', './ds-dialog.css'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DsPlaygroundComponent {
  private readonly destroyRef = inject(DestroyRef);
  readonly overlay = viewChild.required<ElementRef<HTMLDialogElement>>('overlay');
  private readonly timers = new Set<ReturnType<typeof setTimeout>>();
  readonly buttonVariants = [
    { css: 'primary', name: 'Primary', label: 'Approve & Send' },
    { css: 'secondary', name: 'Secondary', label: 'Salva bozza' },
    { css: 'outline', name: 'Outline', label: 'Visualizza email' },
    { css: 'ghost', name: 'Ghost', label: 'Annulla' },
    { css: 'danger', name: 'Danger', label: 'Escalate' }
  ];
  readonly buttonStates = ['Default', 'Hover', 'Active', 'Disabled', 'Loading'];
  readonly loading = signal(false);
  readonly search = signal('');
  readonly email = signal('giulia.rossi@');
  readonly emailInvalid = computed(() => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.email()));
  readonly draft = signal('Gentile Giulia,\n\ngrazie per averci contattato. Per completare l’immatricolazione al corso di Laurea in Informatica, puoi accedere alla tua area riservata sul portale Esse3 e seguire la procedura guidata.\n\nLa certificazione ISEE può essere integrata successivamente, entro i termini indicati nel bando. Trovi il dettaglio nella guida allegata.\n\nUn cordiale saluto,\nSegreteria Studenti · Università della Calabria');
  readonly characterCount = computed(() => this.draft().length);
  readonly generating = signal(false);
  readonly provider = signal('Google');
  readonly model = signal('balanced');
  readonly autoClassify = signal(true);
  readonly notifyReview = signal(false);
  readonly verified = signal(true);
  readonly categories = ['Immatricolazioni', 'Tasse e contributi', 'Carriera universitaria', 'Borse di studio'];
  readonly selectedCategories = signal(['Immatricolazioni', 'Tasse e contributi']);
  readonly models = [
    { id: 'fast', title: 'Veloce', description: 'Classificazione e richieste semplici', meta: 'Bassa latenza', icon: 'cursor' },
    { id: 'balanced', title: 'Bilanciato', description: 'Il giusto equilibrio per ogni email', meta: 'Consigliato', icon: 'sparkle' },
    { id: 'advanced', title: 'Avanzato', description: 'Ragionamento e casi complessi', meta: 'Più contesto', icon: 'layers' }
  ];
  readonly files = signal<string[]>([]);
  readonly fileError = signal('');
  readonly dragging = signal(false);
  readonly sourceOpen = signal(true);
  readonly tags = signal(['Immatricolazioni', 'Tasse e contributi', 'Carriera universitaria']);
  readonly statuses = [
    { label: 'UNREAD', display: 'Non letta', tone: 'neutral', icon: 'mail' },
    { label: 'CLASSIFYING', display: 'AI in elaborazione', tone: 'info', icon: 'sparkle' },
    { label: 'DRAFT_READY', display: 'Bozza pronta', tone: 'warning', icon: 'file' },
    { label: 'ESCALATED', display: 'Intervento richiesto', tone: 'danger', icon: 'warning' },
    { label: 'SENT', display: 'Inviata', tone: 'success', icon: 'check' },
    { label: 'ERROR', display: 'Errore', tone: 'danger', icon: 'close' }
  ];
  readonly emailTabs = ['Tutte', 'Da rivedere', 'Inviate'];
  readonly emailTab = signal('Tutte');
  readonly emails = [
    { id: 'thread_8f2a', initials: 'GR', sender: 'Giulia Rossi', subject: 'Informazioni sulla procedura di immatricolazione', preview: 'Buongiorno, vorrei sapere quali documenti sono necessari per completare…', category: 'Immatricolazioni', state: 'Bozza pronta', tone: 'warning', time: '10:42', unread: true },
    { id: 'thread_7c1b', initials: 'ML', sender: 'Marco Leone', subject: 'Scadenza seconda rata e attestazione ISEE', preview: 'Ho ricevuto un avviso di pagamento, ma ho già caricato la certificazione…', category: 'Tasse e contributi', state: 'Intervento richiesto', tone: 'danger', time: '10:28', unread: false },
    { id: 'thread_6a9d', initials: 'SF', sender: 'Sara Ferraro', subject: 'Conferma iscrizione al secondo anno', preview: 'Gentile Sara, la tua iscrizione risulta correttamente registrata sul portale.', category: 'Carriera universitaria', state: 'Inviata', tone: 'success', time: '09:56', unread: false }
  ];
  readonly filteredEmails = computed(() => this.emails.filter(e => this.emailTab() === 'Tutte' || (this.emailTab() === 'Inviate' ? e.tone === 'success' : e.tone !== 'success')));
  readonly view = signal('Elenco');
  readonly skeleton = signal(true);
  readonly overlayMode = signal<'confirm' | 'drawer'>('confirm');
  readonly selectedThread = signal(this.emails[0]);
  readonly toast = signal<{ text: string; tone: Tone } | null>(null);
  private toastTimer?: ReturnType<typeof setTimeout>;

  constructor() { this.destroyRef.onDestroy(() => this.timers.forEach(timer => clearTimeout(timer))); }
  private later(action: () => void, delay: number): ReturnType<typeof setTimeout> {
    const timer = setTimeout(() => { this.timers.delete(timer); action(); }, delay);
    this.timers.add(timer);
    return timer;
  }
  notify(text: string, tone: Tone = 'success'): void {
    clearTimeout(this.toastTimer);
    if (this.toastTimer) this.timers.delete(this.toastTimer);
    this.toast.set({ text, tone });
    this.toastTimer = this.later(() => this.toast.set(null), 4500);
  }
  simulateSend(): void {
    this.loading.set(true);
    this.later(() => { this.loading.set(false); this.notify('Demo · Email inviata con successo tramite Gmail'); }, 1600);
  }
  regenerate(): void {
    if (this.generating()) return;
    this.generating.set(true);
    this.later(() => {
      this.draft.set('Gentile Giulia,\n\nper completare l’immatricolazione accedi a Esse3 e seleziona “Segreteria → Immatricolazione”. Prepara un documento di identità, il codice fiscale e una fototessera.\n\nPuoi presentare l’ISEE successivamente, rispettando la scadenza indicata nel bando. Il pagamento della prima rata è disponibile nella sezione “Pagamenti”.\n\nRestiamo a disposizione.\nSegreteria Studenti · Università della Calabria');
      this.generating.set(false); this.notify('Demo · Nuova bozza generata', 'info');
    }, 1300);
  }
  insertTemplate(): void { this.draft.update(value => value + '\n\nPer ulteriori informazioni, consulta la guida sul portale studenti.'); }
  toggleCategory(category: string): void { this.selectedCategories.update(values => values.includes(category) ? values.filter(v => v !== category) : [...values, category]); }
  removeTag(tag: string): void { this.tags.update(tags => tags.filter(t => t !== tag)); }
  removeFile(file: string): void { this.files.update(files => files.filter(value => value !== file)); }
  selectFiles(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.acceptFiles(input.files); input.value = '';
  }
  dropFiles(event: DragEvent): void { event.preventDefault(); this.dragging.set(false); this.acceptFiles(event.dataTransfer?.files); }
  private acceptFiles(files: FileList | null | undefined): void {
    const list = Array.from(files ?? []);
    const valid = list.filter(file => /\.(pdf|docx|png|jpe?g)$/i.test(file.name) && file.size <= 10 * 1024 * 1024);
    this.files.update(current => [...new Set([...current, ...valid.map(file => file.name)])]);
    this.fileError.set(valid.length !== list.length ? 'Alcuni file non sono validi. Usa PDF, DOCX, PNG o JPG fino a 10 MB ciascuno.' : '');
  }
  openOverlay(mode: 'confirm' | 'drawer'): void { this.overlayMode.set(mode); this.overlay().nativeElement.showModal(); }
  openThread(thread: typeof this.emails[number]): void { this.selectedThread.set(thread); this.openOverlay('drawer'); }
  closeOverlayOnBackdrop(event: MouseEvent): void { if (event.target === event.currentTarget) this.closeOverlay(); }
  closeOverlay(): void { this.overlay().nativeElement.close(); }
  confirmSend(): void { this.closeOverlay(); this.notify('Demo · Email inviata con successo tramite Gmail'); }
  tabKey(event: KeyboardEvent, index: number): void {
    let target = index;
    if (event.key === 'ArrowRight') target = (index + 1) % this.emailTabs.length;
    else if (event.key === 'ArrowLeft') target = (index + this.emailTabs.length - 1) % this.emailTabs.length;
    else if (event.key === 'Home') target = 0;
    else if (event.key === 'End') target = this.emailTabs.length - 1;
    else return;
    event.preventDefault(); this.emailTab.set(this.emailTabs[target]);
    (event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[target]?.focus();
  }
}
