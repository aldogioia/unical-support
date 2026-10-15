import { Location } from '@angular/common';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AppComponent } from '../../app.component';
import { routes } from '../../app.routes';
import { AuthService } from '../../core/services/auth.service';

describe('Design system route isolation', () => {
  it('opens directly without mounting the application sidebar or requiring authentication', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter(routes), { provide: AuthService, useValue: { isAuthenticated: false, currentUser: signal(null) } }]
    }).compileComponents();
    spyOn(TestBed.inject(Location), 'path').and.returnValue('/design-system');
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-side-navbar')).toBeNull();
    await TestBed.inject(Router).navigateByUrl('/design-system');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-design-system')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('app-feedback-button')).toBeNull();
    await TestBed.inject(Router).navigateByUrl('/login');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-design-system')).toBeNull();
    expect(fixture.nativeElement.querySelector('app-side-navbar')).toBeNull();
    expect(fixture.nativeElement.querySelector('app-design-system')).toBeNull();
    expect(getComputedStyle(fixture.nativeElement).getPropertyValue('--ds-color-primary').trim()).toBeTruthy();
    fixture.destroy();
  });
});
