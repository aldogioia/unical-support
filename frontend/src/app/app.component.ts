import {
  Component,
  ChangeDetectionStrategy,
  signal,
  inject,
  OnInit,
} from '@angular/core';
import { Location } from '@angular/common';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { SideNavbarComponent } from './core/layout/side-navbar/side-navbar.component';
import { FeedbackButtonComponent } from './shared/components/feedback-button/feedback-button.component';
import { ThemePreferencesService } from './core/services/theme-preferences.service';
import { ShellUiService } from './core/services/shell-ui.service';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SideNavbarComponent, FeedbackButtonComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent implements OnInit {
  title = 'unical-support';
  readonly theme = inject(ThemePreferencesService);
  readonly shell = inject(ShellUiService);

  private router = inject(Router);
  private location = inject(Location);
  private authService = inject(AuthService);

  // Login e laboratorio di design hanno un layout indipendente.
  // Location conosce il percorso anche prima della prima NavigationEnd.
  showChrome = signal(!this.isStandalonePage(this.location.path()));

  private isStandalonePage(url: string): boolean {
    return (
      url.startsWith('/login') || /^\/design-system\/?(?:[?#]|$)/.test(url)
    );
  }

  ngOnInit() {
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        this.showChrome.set(!this.isStandalonePage(e.urlAfterRedirects));
        this.shell.closeNavigation();
      });

    // Se c'è già un token salvato da una sessione precedente, ricarica l'utente corrente
    if (this.authService.isAuthenticated) {
      this.authService.loadCurrentUser();
    }
  }
}
