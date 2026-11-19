import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { EmailSource } from '../../../core/api/models/email-source';
import { DsIconComponent } from '../ds-icon/ds-icon.component';

@Component({
  selector: 'app-retrieved-sources', standalone: true, imports: [DsIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <details class="sources">
      <summary><ds-icon name="book" /><span>Fonti consultate</span>
        <span class="count">{{ groups().length ? groups().length + (groups().length === 1 ? ' documento' : ' documenti') : (sources() == null ? 'Non registrate' : 'Nessuna fonte trovata') }}</span>
        <ds-icon name="down" />
      </summary>
      @if (sources() == null) {
        <p class="empty">Per questa bozza non è stato registrato lo storico delle fonti. Le nuove generazioni conservano i documenti e i frammenti recuperati.</p>
      } @else if (!groups().length) {
        <p class="empty">La ricerca non ha restituito frammenti documentali utilizzabili.</p>
      } @else {
        <p class="note">Documenti recuperati durante la generazione AI. Verifica che supportino anche le eventuali modifiche alla bozza.</p>
        @for (group of groups(); track group.key) {
          <article>
            <h4><ds-icon name="file" />{{ group.source.source_name }}</h4>
            @if (group.source.reference_url) {
              <a [href]="group.source.reference_url" target="_blank" rel="noopener noreferrer">Apri documento pubblico <ds-icon name="arrow" /></a>
            } @else { <small>Link pubblico non disponibile</small> }
            @for (fragment of group.fragments; track $index) {
              @if (fragment.page != null) { <small class="page">Pagina {{ fragment.page }}</small> }
              <blockquote>{{ fragment.excerpt }}</blockquote>
            }
          </article>
        }
      }
    </details>
  `,
  styles: [`
    :host{display:block;margin-top:13px}.sources{border:var(--ds-container-stroke) solid var(--ds-border);border-radius:8px;background:var(--ds-surface)}
    summary{display:flex;align-items:center;gap:9px;padding:13px 15px;list-style:none;cursor:pointer;color:var(--ds-text-primary);font-size:12px}summary::-webkit-details-marker{display:none}
    ds-icon{width:16px;height:16px;flex:none}.count{margin-left:auto;font-size:11px;color:var(--ds-text-secondary)}
    .empty,.note{padding:0 15px 15px;margin:0;font-size:12px;line-height:1.6;color:var(--ds-text-secondary)}
    article{margin:0 15px 16px;padding-top:12px;border-top:1px solid var(--ds-divider)}h4{display:flex;gap:8px;align-items:center;font-size:12px;font-weight:500;margin:0 0 8px;overflow-wrap:anywhere}
    a{display:inline-flex;align-items:center;gap:5px;color:var(--ds-color-primary-700);font-size:12px}small{font-size:11px;color:var(--ds-text-muted)}.page{display:block;margin-top:12px}
    blockquote{margin:8px 0 0;padding:8px 12px;border-left:2px solid var(--ds-border);font-size:12px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--ds-text-secondary)}
  `],
})
export class RetrievedSourcesComponent {
  readonly sources = input<EmailSource[] | null | undefined>(null);
  readonly groups = computed(() => {
    const groups = new Map<string, { key: string; source: EmailSource; fragments: EmailSource[] }>();
    for (const source of this.sources() ?? []) {
      const key = JSON.stringify([source.document_id, source.source_name, source.reference_url]);
      if (!groups.has(key)) groups.set(key, { key, source, fragments: [] });
      groups.get(key)!.fragments.push(source);
    }
    return Array.from(groups.values());
  });
}
