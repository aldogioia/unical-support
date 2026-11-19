import {
  TestBed,
  fakeAsync,
  flushMicrotasks,
  tick,
} from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Api } from '../../../../core/api/api';
import { updateAiSettingsApiAiSettingsPut } from '../../../../core/api/fn/ai-settings/update-ai-settings-api-ai-settings-put';
import { listLocalModelsApiAiSettingsLocalModelsGet } from '../../../../core/api/fn/ai-settings/list-local-models-api-ai-settings-local-models-get';
import { readAiSettingsApiAiSettingsGet } from '../../../../core/api/fn/ai-settings/read-ai-settings-api-ai-settings-get';
import { CLOUD_MODELS, ModelSettingsComponent } from './model-settings.component';
import { ThemePreferencesService } from '../../../../core/services/theme-preferences.service';

const settings = {
  id: 'settings-1',
  classifier_provider: 'groq',
  classifier_model: 'classifier-model',
  classifier_base_url: null,
  responder_provider: 'google',
  responder_model: 'responder-model',
  responder_base_url: null,
};
describe('Settings appearance and AI configuration', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(async () => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.returnValue(Promise.resolve(settings) as any);
    await TestBed.configureTestingModule({
      imports: [ModelSettingsComponent],
      providers: [provideRouter([]), { provide: Api, useValue: api }],
    }).compileComponents();
  });
  it('changes appearance immediately without writing AI settings', fakeAsync(() => {
    const fixture = TestBed.createComponent(ModelSettingsComponent);
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    const before = api.invoke.calls.count();
    const service = TestBed.inject(ThemePreferencesService),
      initial = { ...service.preferences() };
    fixture.nativeElement
      .querySelector('input[name=contrast][value=high]')
      .click();
    fixture.detectChanges();
    expect(document.documentElement.dataset['contrast']).toBe('high');
    expect(api.invoke.calls.count()).toBe(before);
    service.update(initial);
    fixture.detectChanges();
    fixture.destroy();
  }));
  it('shows both agents and saves the same provider/model/base URL contract', fakeAsync(() => {
    const fixture = TestBed.createComponent(ModelSettingsComponent),
      component = fixture.componentInstance;
    fixture.detectChanges();
    flushMicrotasks();
    component.tab.set('ai');
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.agent-card').length).toBe(
      2,
    );
    expect(fixture.nativeElement.querySelector('#classifier-model').value).toBe(
      'classifier-model',
    );
    component.form.classifier_provider = 'local';
    component.form.classifier_base_url = ' http://model-host:11434/v1 ';
    api.invoke.and.returnValue(Promise.resolve(settings) as any);
    component.save();
    flushMicrotasks();
    expect(api.invoke).toHaveBeenCalledWith(updateAiSettingsApiAiSettingsPut, {
      body: {
        classifier_provider: 'local',
        classifier_model: 'classifier-model',
        classifier_base_url: 'http://model-host:11434/v1',
        responder_provider: 'google',
        responder_model: 'responder-model',
        responder_base_url: null,
      },
    });
    expect(component.saved()).toBeTrue();
    tick(3000);
    fixture.destroy();
  }));
});

describe('Model name drop-down', () => {
  let api: jasmine.SpyObj<Api>;
  let stored: any;
  let local: () => Promise<any>;
  beforeEach(async () => {
    stored = { ...settings, classifier_model: 'llama-3.3-70b-versatile', responder_model: 'gemini-3.5-flash-lite' };
    local = () => Promise.resolve({ base_url: 'http://gpu:11434/v1', models: ['gemma3:12b', 'kimi-k2'] });
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.callFake(((operation: unknown) => {
      if (operation === listLocalModelsApiAiSettingsLocalModelsGet) return local();
      if (operation === readAiSettingsApiAiSettingsGet) return Promise.resolve(stored);
      return Promise.resolve(stored);
    }) as any);
    await TestBed.configureTestingModule({
      imports: [ModelSettingsComponent],
      providers: [provideRouter([]), { provide: Api, useValue: api }],
    }).compileComponents();
  });

  function open() {
    const fixture = TestBed.createComponent(ModelSettingsComponent);
    fixture.componentInstance.tab.set('ai');
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    return fixture;
  }
  const options = (fixture: any, id: string) =>
    Array.from(fixture.nativeElement.querySelectorAll(`#${id} option`)).map((o: any) => o.value);

  it('lists only the high-quota Groq and Gemini models in a select', fakeAsync(() => {
    const fixture = open();
    expect(fixture.nativeElement.querySelector('select#classifier-model')).not.toBeNull();
    expect(options(fixture, 'classifier-model')).toEqual(CLOUD_MODELS['groq'].map((m) => m.id));
    expect(options(fixture, 'responder-model')).toEqual([
      'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemma-4-31b-it', 'gemma-4-26b-a4b-it',
    ]);
    expect(options(fixture, 'classifier-model')).not.toContain('whisper-large-v3');
    fixture.destroy();
  }));

  it('keeps a saved model that is not in the list', fakeAsync(() => {
    stored = { ...settings };
    const fixture = open();
    const values = options(fixture, 'classifier-model');
    expect(values[0]).toBe('classifier-model');
    expect(fixture.nativeElement.querySelector('#classifier-model option').textContent).toContain('(attuale)');
    fixture.destroy();
  }));

  it('switching provider picks the first model of the new provider', fakeAsync(() => {
    const fixture = open(),
      component = fixture.componentInstance;
    component.onProviderChange(component.agents[0], 'google');
    expect(component.form.classifier_model).toBe('gemini-3.5-flash-lite');
    fixture.destroy();
  }));

  it('loads the models of a local server when it is selected', fakeAsync(() => {
    const fixture = open(),
      component = fixture.componentInstance;
    component.form.classifier_base_url = ' http://gpu:11434/v1 ';
    component.onProviderChange(component.agents[0], 'local');
    flushMicrotasks();
    fixture.detectChanges();
    expect(api.invoke).toHaveBeenCalledWith(listLocalModelsApiAiSettingsLocalModelsGet, {
      base_url: 'http://gpu:11434/v1',
    });
    expect(options(fixture, 'classifier-model')).toEqual(['llama-3.3-70b-versatile', 'gemma3:12b', 'kimi-k2']);
    expect(fixture.nativeElement.querySelector('.model-ok').textContent).toContain('2 modelli');
    fixture.destroy();
  }));

  it('loads local models on start and shows a clear error when the server is unreachable', fakeAsync(() => {
    stored = { ...settings, responder_provider: 'local', responder_model: 'gemma3:12b',
      responder_base_url: 'http://localhost:11434/v1' };
    local = () => Promise.reject({ status: 502, error: { detail: 'Connection refused' } });
    const fixture = open();
    expect(api.invoke).toHaveBeenCalledWith(listLocalModelsApiAiSettingsLocalModelsGet, {
      base_url: 'http://localhost:11434/v1',
    });
    const error = fixture.nativeElement.querySelector('.model-error').textContent;
    expect(error).toContain('http://localhost:11434/v1');
    expect(error).toContain('Connection refused');
    const input = fixture.nativeElement.querySelector('input#responder-model');
    expect(input).not.toBeNull();
    expect(input.value).toBe('gemma3:12b');
    fixture.destroy();
  }));

  it('asks for the URL before listing local models', fakeAsync(() => {
    const fixture = open(),
      component = fixture.componentInstance;
    component.form.responder_base_url = '';
    component.onProviderChange(component.agents[1], 'local');
    flushMicrotasks();
    expect(api.invoke).not.toHaveBeenCalledWith(listLocalModelsApiAiSettingsLocalModelsGet, jasmine.anything());
    expect(component.localState(component.agents[1]).error).toContain("Inserisci l'URL");
    fixture.destroy();
  }));

  it('lets the admin type a local model name that is not in ollama list', fakeAsync(() => {
    const fixture = open(),
      component = fixture.componentInstance;
    component.form.classifier_base_url = 'http://gpu:11434/v1';
    component.onProviderChange(component.agents[0], 'local');
    flushMicrotasks();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('select#classifier-model')).not.toBeNull();
    fixture.nativeElement.querySelector('.model-mode').click();
    fixture.detectChanges();
    flushMicrotasks();
    const input: HTMLInputElement = fixture.nativeElement.querySelector('input#classifier-model');
    expect(input).not.toBeNull();
    input.value = 'qwen3:32b-custom';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(component.form.classifier_model).toBe('qwen3:32b-custom');
    fixture.nativeElement.querySelector('.model-mode').click();
    fixture.detectChanges();
    flushMicrotasks();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('select#classifier-model')).not.toBeNull();
    expect(options(fixture, 'classifier-model')[0]).toBe('qwen3:32b-custom');
    fixture.destroy();
  }));
});
