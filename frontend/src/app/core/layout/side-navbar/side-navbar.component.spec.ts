import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { SideNavbarComponent } from './side-navbar.component';

describe('Sidebar profile', () => {
  it('shows only the email local part, retains the full address as a tooltip and supports logout', () => {
    const auth = { currentUser: signal({ email: 'aldo.gioia@example.org' }), isAuthenticated: true, logout: jasmine.createSpy('logout') };
    TestBed.configureTestingModule({ imports: [SideNavbarComponent], providers: [provideRouter([]), { provide: AuthService, useValue: auth }] });
    const fixture = TestBed.createComponent(SideNavbarComponent);
    fixture.detectChanges();
    const address = fixture.nativeElement.querySelector('.operator-address');
    expect(address.textContent.trim()).toBe('aldo.gioia');
    expect(address.title).toBe('aldo.gioia@example.org');
    expect(fixture.nativeElement.querySelector('.operator').textContent).not.toContain('@');
    expect(fixture.nativeElement.querySelector('ds-icon hugeicons-icon svg')).not.toBeNull();
    fixture.nativeElement.querySelector('button[aria-label="Esci"]').click();
    expect(auth.logout).toHaveBeenCalledTimes(1);
  });
  it('opens feedback from a navigation item, closes mobile navigation and respects busy state', () => {
    const auth = { currentUser: signal(null), isAuthenticated: false };
    TestBed.configureTestingModule({ imports: [SideNavbarComponent], providers: [provideRouter([]), { provide: AuthService, useValue: auth }] });
    const fixture = TestBed.createComponent(SideNavbarComponent);
    fixture.detectChanges();
    fixture.componentInstance.shell.mobileOpen.set(true);
    const request = jasmine.createSpy('feedbackRequested');
    fixture.componentInstance.feedbackRequested.subscribe(request);
    const button = fixture.nativeElement.querySelector('button[aria-label="Segnalazioni"]') as HTMLButtonElement;
    expect(button.classList.contains('nav-link')).toBeTrue();
    button.click();
    expect(fixture.componentInstance.shell.mobileOpen()).toBeFalse();
    expect(request).toHaveBeenCalledTimes(1);
    fixture.componentRef.setInput('feedbackBusy', true); fixture.detectChanges();
    expect(button.disabled).toBeTrue();
    button.click(); expect(request).toHaveBeenCalledTimes(1);
  });

});
