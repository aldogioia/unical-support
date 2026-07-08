import { Component, ChangeDetectionStrategy, signal, inject, OnInit } from '@angular/core';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { SideNavbarComponent } from './core/layout/side-navbar/side-navbar.component';
import { FeedbackButtonComponent } from './shared/components/feedback-button/feedback-button.component';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SideNavbarComponent, FeedbackButtonComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AppComponent implements OnInit {
  title = 'unical-support';

  private router = inject(Router);
  private authService = inject(AuthService);

  // Sidebar e feedback widget non vanno mostrati nella pagina di login
  showChrome = signal(!this.router.url.startsWith('/login'));

  ngOnInit() {
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd)
    ).subscribe((e) => {
      this.showChrome.set(!e.urlAfterRedirects.startsWith('/login'));
    });

    // Se c'è già un token salvato da una sessione precedente, ricarica l'utente corrente
    if (this.authService.isAuthenticated) {
      this.authService.loadCurrentUser();
    }
  }
}
