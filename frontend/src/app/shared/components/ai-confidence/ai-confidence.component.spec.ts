import { TestBed } from '@angular/core/testing';
import { AiConfidenceComponent } from './ai-confidence.component';

describe('Compact AI confidence', () => {
  [
    { value: 0.96, label: '96%', tone: 'success' },
    { value: 0.65, label: '65%', tone: 'warning' },
    { value: 0, label: '0%', tone: 'danger' },
    { value: null, label: 'N/D', tone: 'info' },
    { value: NaN, label: 'N/D', tone: 'info' },
    { value: 96, label: 'N/D', tone: 'info' },
  ].forEach(({ value, label, tone }) => {
    it(`renders ${label} with the ${tone} tone for ${value}`, () => {
      const fixture = TestBed.createComponent(AiConfidenceComponent);
      fixture.componentRef.setInput('value', value);
      fixture.detectChanges();
      const pill = fixture.nativeElement.querySelector('.confidence-pill');
      expect(pill.textContent).toContain(label);
      expect(pill.classList.contains(tone)).toBeTrue();
      expect(pill.getAttribute('aria-label')).toContain(label);
      expect(pill.title).toContain(label === 'N/D' ? 'non disponibile' : 'Non è una probabilità');
    });
  });
});
