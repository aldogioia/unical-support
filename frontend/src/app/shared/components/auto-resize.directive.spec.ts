import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { AutoResizeDirective } from './auto-resize.directive';

@Component({ standalone: true, imports: [AutoResizeDirective], template: '<textarea appAutoResize [value]="text()" style="width:220px;min-height:40px;padding:10px;border:1px solid;box-sizing:border-box"></textarea>' })
class EditorHost { text = signal('Testo iniziale'); }

describe('Answer editor auto resize', () => {
  it('fits initial content, expands programmatic and typed text, then shrinks after deletion', () => {
    const fixture = TestBed.createComponent(EditorHost);
    fixture.detectChanges();
    const field = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
    const initial = field.offsetHeight;
    fixture.componentInstance.text.set(Array(30).fill('Paragrafo della risposta.').join('\n'));
    fixture.detectChanges();
    expect(field.offsetHeight).toBeGreaterThan(initial * 2);
    expect(field.scrollHeight).toBeLessThanOrEqual(field.clientHeight + 1);
    const expanded = field.offsetHeight;
    field.value += '\n' + Array(30).fill('Altra riga').join('\n');
    field.dispatchEvent(new Event('input'));
    expect(field.offsetHeight).toBeGreaterThan(expanded);
    field.value = 'Breve';
    field.dispatchEvent(new Event('input'));
    expect(field.offsetHeight).toBeLessThan(expanded);
    expect(field.style.overflowY).toBe('hidden');
    fixture.destroy();
  });
});
