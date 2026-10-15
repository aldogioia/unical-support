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
    } catch (e) {
      console.error(e);
      this.error.set('Impossibile caricare la configurazione dei modelli.');
    } finally {
      this.loading.set(false);
    }
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
