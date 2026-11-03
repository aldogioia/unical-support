import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  signal,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ThemePreferencesService } from '../../../../core/services/theme-preferences.service';
import { DsIconComponent } from '../../../../shared/components/ds-icon/ds-icon.component';
import { WorkspaceHeaderComponent } from '../../../../shared/components/workspace-header/workspace-header.component';
import { RouterLink } from '@angular/router';
import { Api } from '../../../../core/api/api';
import { readAiSettingsApiAiSettingsGet } from '../../../../core/api/fn/ai-settings/read-ai-settings-api-ai-settings-get';
import { updateAiSettingsApiAiSettingsPut } from '../../../../core/api/fn/ai-settings/update-ai-settings-api-ai-settings-put';
import { AiSettingsResponse } from '../../../../core/api/models/ai-settings-response';
import { listLocalModelsApiAiSettingsLocalModelsGet } from '../../../../core/api/fn/ai-settings/list-local-models-api-ai-settings-local-models-get';

export interface ModelOption {
  id: string;
  label: string;
}

/**
 * Modelli dei provider online proposti nel menu a tendina. Solo modelli di testo
 * con un limite di richieste giornaliere sufficiente per email e documenti:
 * quelli da 20 richieste al giorno si esaurirebbero in pochi minuti.
 */
export const CLOUD_MODELS: Record<string, ModelOption[]> = {
  groq: [
    { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B · llama-3.3-70b-versatile' },
    { id: 'openai/gpt-oss-120b', label: 'GPT OSS 120B · openai/gpt-oss-120b' },
    { id: 'openai/gpt-oss-20b', label: 'GPT OSS 20B · openai/gpt-oss-20b' },
    { id: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B (veloce) · llama-3.1-8b-instant' },
  ],
  google: [
    { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite · 500 richieste/giorno' },
    { id: 'gemini-3.1-flash-lite', label: 'Gemini 3.1 Flash Lite · 500 richieste/giorno' },
    { id: 'gemma-4-31b-it', label: 'Gemma 4 31B · 14.400 richieste/giorno, max 16K token/min' },
    { id: 'gemma-4-26b-a4b-it', label: 'Gemma 4 26B · 14.400 richieste/giorno, max 16K token/min' },
  ],
};

export type AgentId = 'classifier' | 'responder';

export interface LocalModelsState {
  status: 'idle' | 'loading' | 'ok' | 'error';
  models: string[];
  error: string;
  url: string;
}

type AgentConfig = ModelSettingsComponent['agents'][number];

const IDLE_LOCAL: LocalModelsState = { status: 'idle', models: [], error: '', url: '' };

@Component({
  selector: 'app-model-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    DsIconComponent,
    WorkspaceHeaderComponent,
    RouterLink,
  ],
  templateUrl: './model-settings.component.html',
  styleUrls: ['./model-settings.component.css', './model-settings-ai.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModelSettingsComponent implements OnInit {
  private api = inject(Api);
  readonly theme = inject(ThemePreferencesService);
  readonly tab = signal<'appearance' | 'ai'>('appearance');
  readonly agents = [
    {
      id: 'classifier',
      title: 'Agente Classificatore',
      subtitle: 'Triage & categorizzazione',
      description:
        'Riconosce l’argomento delle email e le associa alla tassonomia.',
      icon: 'tag',
      provider: 'classifier_provider',
      model: 'classifier_model',
      url: 'classifier_base_url',
    },
    {
      id: 'responder',
      title: 'Agente Risponditore',
      subtitle: 'RAG & generazione bozze',
      description:
        'Prepara risposte contestualizzate a partire dalle fonti documentali.',
      icon: 'mail',
      provider: 'responder_provider',
      model: 'responder_model',
      url: 'responder_base_url',
    },
  ] as const;

  readonly localModels = signal<Record<AgentId, LocalModelsState>>({
    classifier: IDLE_LOCAL,
    responder: IDLE_LOCAL,
  });

  /** Per il server locale: l'admin preferisce scrivere il nome del modello invece di sceglierlo dalla lista. */
  readonly manualModel = signal<Record<AgentId, boolean>>({
    classifier: false,
    responder: false,
  });

  loading = signal<boolean>(true);
  saving = signal<boolean>(false);
  saved = signal<boolean>(false);
  error = signal<string | null>(null);

  form = {
    classifier_provider: '',
    classifier_model: '',
    classifier_base_url: '' as string | null,
    responder_provider: '',
    responder_model: '',
    responder_base_url: '' as string | null,
  };

  providers = [
    { value: 'groq', label: 'Groq (online)' },
    { value: 'google', label: 'Google Gemini (online)' },
    { value: 'local', label: 'OpenAI-compatible / Server locale' },
  ];

  ngOnInit() {
    this.load();
  }

  async load() {
    this.loading.set(true);
    this.error.set(null);
    try {
      const data: AiSettingsResponse = await this.api.invoke(
        readAiSettingsApiAiSettingsGet,
        {},
      );
      this.form = {
        classifier_provider: data.classifier_provider,
        classifier_model: data.classifier_model,
        classifier_base_url: data.classifier_base_url ?? '',
        responder_provider: data.responder_provider,
        responder_model: data.responder_model,
        responder_base_url: data.responder_base_url ?? '',
      };
      for (const agent of this.agents) {
        if (this.form[agent.provider] === 'local' && this.form[agent.url]?.trim()) {
          void this.loadLocalModels(agent);
        }
      }
    } catch (e) {
      console.error(e);
      this.error.set('Impossibile caricare la configurazione dei modelli.');
    } finally {
      this.loading.set(false);
    }
  }

  localState(agent: { id: AgentId }): LocalModelsState {
    return this.localModels()[agent.id];
  }

  /** Opzioni del menu: il modello salvato resta sempre selezionabile, anche se non è in lista. */
  modelOptions(agent: AgentConfig): ModelOption[] {
    const provider = this.form[agent.provider];
    const current = this.form[agent.model]?.trim();
    const options =
      provider === 'local'
        ? this.localState(agent).models.map((id) => ({ id, label: id }))
        : CLOUD_MODELS[provider] ?? [];
    if (current && !options.some((option) => option.id === current)) {
      return [{ id: current, label: `${current} (attuale)` }, ...options];
    }
    return options;
  }

  /** Campo di testo libero solo se la lista non è disponibile (server locale irraggiungibile o provider sconosciuto). */
  useManualModel(agent: AgentConfig): boolean {
    const provider = this.form[agent.provider];
    if (provider === 'local') {
      return this.manualModel()[agent.id] || this.localState(agent).status === 'error';
    }
    return !CLOUD_MODELS[provider];
  }

  setManualModel(agent: AgentConfig, manual: boolean): void {
    this.manualModel.update((all) => ({ ...all, [agent.id]: manual }));
    const models = this.localState(agent).models;
    // Tornando alla lista con un nome vuoto, si propone il primo modello disponibile.
    if (!manual && !this.form[agent.model]?.trim() && models.length) {
      this.form[agent.model] = models[0];
    }
  }

  onProviderChange(agent: AgentConfig, provider: string): void {
    this.form[agent.provider] = provider;
    const cloud = CLOUD_MODELS[provider];
    if (cloud && !cloud.some((option) => option.id === this.form[agent.model])) {
      this.form[agent.model] = cloud[0].id;
    }
    if (provider === 'local') void this.loadLocalModels(agent);
  }

  onUrlCommitted(agent: AgentConfig): void {
    const url = this.form[agent.url]?.trim() ?? '';
    const state = this.localState(agent);
    if (state.status === 'loading' || (url && url === state.url && state.status === 'ok')) return;
    void this.loadLocalModels(agent);
  }

  async loadLocalModels(agent: AgentConfig): Promise<void> {
    const url = this.form[agent.url]?.trim() ?? '';
    if (!url) {
      this.setLocal(agent.id, {
        status: 'error',
        models: [],
        url: '',
        error: "Inserisci l'URL del server per vedere i modelli disponibili.",
      });
      return;
    }
    this.setLocal(agent.id, { ...this.localState(agent), status: 'loading', error: '', url });
    try {
      const result = await this.api.invoke(listLocalModelsApiAiSettingsLocalModelsGet, {
        base_url: url,
      });
      if ((this.form[agent.url]?.trim() ?? '') !== url) return; // l'URL è cambiato nel frattempo
      this.setLocal(agent.id, { status: 'ok', models: result.models, error: '', url });
      if (!this.form[agent.model]?.trim() && result.models.length) {
        this.form[agent.model] = result.models[0];
      }
    } catch (e: any) {
      if ((this.form[agent.url]?.trim() ?? '') !== url) return;
      const detail = typeof e?.error?.detail === 'string' ? e.error.detail : '';
      this.setLocal(agent.id, {
        status: 'error',
        models: [],
        url,
        error:
          e?.status === 403
            ? 'Solo un amministratore può leggere la lista dei modelli.'
            : `Il server ${url} non risponde dal backend${detail ? ` (${detail})` : ''}.`,
      });
    }
  }

  private setLocal(id: AgentId, state: LocalModelsState): void {
    this.localModels.update((all) => ({ ...all, [id]: state }));
  }

  async save() {
    if (this.saving()) return;
    this.saving.set(true);
    this.saved.set(false);
    this.error.set(null);
    try {
      const payload = {
        ...this.form,
        classifier_base_url: this.form.classifier_base_url?.trim() || null,
        responder_base_url: this.form.responder_base_url?.trim() || null,
      };
      await this.api.invoke(updateAiSettingsApiAiSettingsPut, {
        body: payload,
      });
      this.saved.set(true);
      setTimeout(() => this.saved.set(false), 3000);
    } catch (e) {
      console.error(e);
      this.error.set('Salvataggio non riuscito. Controlla i valori inseriti.');
    } finally {
      this.saving.set(false);
    }
  }
}
