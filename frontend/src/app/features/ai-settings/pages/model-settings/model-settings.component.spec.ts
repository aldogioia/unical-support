import {
  TestBed,
  fakeAsync,
  flushMicrotasks,
  tick,
} from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Api } from '../../../../core/api/api';
import { updateAiSettingsApiAiSettingsPut } from '../../../../core/api/fn/ai-settings/update-ai-settings-api-ai-settings-put';
import { ModelSettingsComponent } from './model-settings.component';
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
