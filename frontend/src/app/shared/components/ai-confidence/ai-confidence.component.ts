import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DsIconComponent } from '../ds-icon/ds-icon.component';

@Component({
  selector: 'app-ai-confidence', standalone: true, imports: [DsIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="confidence-pill" [class]="'confidence-pill ' + tone()" [title]="description()" [attr.aria-label]="'Confidenza AI: ' + label() + '. ' + description()">
    <ds-icon name="sparkle" /><span>AI confidence</span><strong>{{ label() }}</strong>
  </span>`,
  styles: [`
    :host{display:inline-flex;max-width:100%}
    .confidence-pill{display:inline-flex;align-items:center;gap:5px;padding:2px 7px;border-radius:999px;font-size:10px;line-height:16px;font-weight:500;white-space:nowrap;background:var(--ds-info-soft);color:var(--ds-info)}
    ds-icon{width:12px;height:12px}strong{font-weight:600;font-variant-numeric:tabular-nums}
    .success{background:var(--ds-success-soft);color:var(--ds-success)}
    .warning{background:var(--ds-warning-soft);color:var(--ds-warning)}
    .danger{background:var(--ds-danger-soft);color:var(--ds-danger)}
  `],
})
export class AiConfidenceComponent {
  readonly value = input<number | null | undefined>(null);
  readonly score = computed(() => {
    const value = this.value();
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
  });
  readonly label = computed(() => this.score() === null ? 'N/D' : `${Math.round(this.score()! * 100)}%`);
  readonly tone = computed(() => this.score() === null ? 'info' : this.score()! >= 0.8 ? 'success' : this.score()! >= 0.5 ? 'warning' : 'danger');
  readonly description = computed(() => this.score() === null
    ? 'Dato non disponibile per questa email.'
    : 'Rilevanza media dei frammenti recuperati dal reranker. Non è una probabilità di correttezza della risposta; verifica sempre le fonti.');
}
