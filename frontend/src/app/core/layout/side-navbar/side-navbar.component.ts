import { Component, ChangeDetectionStrategy, inject, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-side-navbar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, CommonModule],
  templateUrl: './side-navbar.component.html',
  styleUrl: './side-navbar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SideNavbarComponent implements OnInit {
  protected authService = inject(AuthService);

  ngOnInit() {
    if (!this.authService.currentUser() && this.authService.isAuthenticated) {
      this.authService.loadCurrentUser();
    }
  }

  logout() {
    this.authService.logout();
  }
}
