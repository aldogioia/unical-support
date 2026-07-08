import { Component, ChangeDetectionStrategy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private authService = inject(AuthService);
  private router = inject(Router);

  email = '';
  password = '';
  loading = signal(false);
  error = signal<string | null>(null);

  async submit() {
    if (!this.email || !this.password || this.loading()) return;

    this.loading.set(true);
    this.error.set(null);
    try {
      await this.authService.login(this.email, this.password);
      this.router.navigate(['/review-hub']);
    } catch (e: any) {
      console.error(e);
      if (e?.status === 401) {
        this.error.set('Email o password errati.');
      } else if (e?.status === 403) {
        this.error.set('Utente non autorizzato o disattivato.');
      } else {
        this.error.set('Errore durante il login. Riprova.');
      }
    } finally {
      this.loading.set(false);
    }
  }
}
