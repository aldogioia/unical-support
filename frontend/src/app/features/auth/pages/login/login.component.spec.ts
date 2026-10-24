import { ComponentFixture, TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { Router } from '@angular/router';
import { AuthService } from '../../../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let auth: jasmine.SpyObj<AuthService>;
  let router: jasmine.SpyObj<Router>;

  beforeEach(async () => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['login']);
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [{ provide: AuthService, useValue: auth }, { provide: Router, useValue: router }],
    }).compileComponents();
    fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
  });

  function fillCredentials() {
    const email = fixture.nativeElement.querySelector('#login-email') as HTMLInputElement;
    const password = fixture.nativeElement.querySelector('#login-password') as HTMLInputElement;
    email.value = 'operatore@example.org';
    password.value = 'test-only-password';
    email.dispatchEvent(new Event('input'));
    password.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function submitForm() {
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
    // NgModel applies disabled states asynchronously after the loading signal changes.
    flushMicrotasks();
    fixture.detectChanges();
  }

  it('prevents empty and duplicate submissions, then navigates after successful login', fakeAsync(() => {
    let finish!: () => void;
    auth.login.and.returnValue(new Promise<void>(resolve => finish = resolve));
    expect(fixture.nativeElement.querySelector('button').disabled).toBeTrue();
    submitForm();
    expect(auth.login).not.toHaveBeenCalled();
    fillCredentials();
    submitForm();
    expect(auth.login).toHaveBeenCalledOnceWith('operatore@example.org', 'test-only-password');
    expect(fixture.nativeElement.querySelector('form').getAttribute('aria-busy')).toBe('true');
    expect(fixture.nativeElement.querySelector('button').textContent).toContain('Accesso in corso');
    expect(fixture.nativeElement.querySelector('button').disabled).toBeTrue();
    expect(fixture.nativeElement.querySelector('#login-email').disabled).toBeTrue();
    expect(fixture.nativeElement.querySelector('#login-password').disabled).toBeTrue();
    submitForm();
    expect(auth.login.calls.count()).toBe(1);
    expect(router.navigate).not.toHaveBeenCalled();
    finish();
    flushMicrotasks();
    fixture.detectChanges();
    expect(router.navigate).toHaveBeenCalledOnceWith(['/review-hub']);
    expect(fixture.nativeElement.querySelector('form').getAttribute('aria-busy')).toBe('false');
  }));

  [
    { status: 401, message: 'Email o password errati.' },
    { status: 403, message: 'Utente non autorizzato o disattivato.' },
    { status: 503, message: 'Errore durante l’accesso. Riprova.' },
  ].forEach(({ status, message }) => {
    it(`announces a ${status} error and allows retry without navigating`, fakeAsync(() => {
      spyOn(console, 'error');
      auth.login.and.returnValue(Promise.reject({ status }));
      fillCredentials();
      submitForm();
      flushMicrotasks();
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(message);
      expect(fixture.nativeElement.querySelector('button').disabled).toBeFalse();
      expect(fixture.nativeElement.querySelector('#login-email').value).toBe('operatore@example.org');
      expect(router.navigate).not.toHaveBeenCalled();
      let finish!: () => void;
      auth.login.and.returnValue(new Promise<void>(resolve => finish = resolve));
      submitForm();
      expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
      finish();
      flushMicrotasks();
    }));
  });
});
