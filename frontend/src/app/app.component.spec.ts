import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { AppComponent } from './app.component';
import { AuthService } from './core/services/auth.service';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideRouter([]), provideHttpClient(),
        { provide: AuthService, useValue: { isAuthenticated: false, currentUser: signal(null) } }
      ]
    }).compileComponents();
  });

  it('shows the Italian navigation without requiring a session', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Revisione email');
    expect(text).toContain('Documenti');
    expect(text).toContain('Categorie');
    expect(text).toContain('Impostazioni');
    expect(text).toContain('Segnalazioni');
    expect(fixture.nativeElement.querySelector('.feedback-fab')).toBeNull();
    fixture.destroy();
  });
});
