import {
  Component,
  ChangeDetectionStrategy,
  inject,
  OnInit,
  computed,
  input,
  output,
  effect,
  ElementRef,
  DestroyRef,
  HostListener,
} from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { DsIconComponent } from '../../../shared/components/ds-icon/ds-icon.component';
import { ShellUiService } from '../../services/shell-ui.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-side-navbar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, CommonModule, DsIconComponent],
  templateUrl: './side-navbar.component.html',
  styleUrl: './side-navbar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SideNavbarComponent implements OnInit {
  readonly feedbackBusy = input(false);
  readonly feedbackRequested = output<void>();
  openFeedback(): void {
    this.shell.closeNavigation();
    this.feedbackRequested.emit();
  }

  protected authService = inject(AuthService);
  readonly shell = inject(ShellUiService);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  constructor() {
    let previousFocus: HTMLElement | null = null;
    let wasOpen = false;
    let frame = 0;
    effect(() => {
      const open = this.shell.mobileOpen();
      if (open) {
        previousFocus = document.activeElement as HTMLElement;
        frame = requestAnimationFrame(() =>
          this.element.nativeElement
            .querySelector<HTMLElement>('.mobile-nav-close')
            ?.focus(),
        );
      } else if (wasOpen && previousFocus?.isConnected)
        previousFocus.focus({ preventScroll: true });
      wasOpen = open;
    });
    inject(DestroyRef).onDestroy(() => cancelAnimationFrame(frame));
  }
  @HostListener('keydown', ['$event']) trapMobileNavigation(
    event: KeyboardEvent,
  ): void {
    if (!this.shell.mobileOpen() || event.key !== 'Tab') return;
    const controls = Array.from(
      this.element.nativeElement.querySelectorAll<HTMLElement>(
        'a[href],button:not(:disabled)',
      ),
    ).filter((control) => control.getClientRects().length > 0);
    const first = controls[0],
      last = controls[controls.length - 1];
    if (!first) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  readonly email = computed(
    () => this.authService.currentUser()?.email || 'Operatore',
  );
  readonly initials = computed(() => {
    const name = this.email().split('@')[0];
    const parts = name.split(/[. _-]/);
    return this.email() === 'Operatore'
      ? 'OP'
      : (parts.length > 1 ? parts.map((word) => word[0]).join('') : name)
          .slice(0, 2)
          .toUpperCase();
  });

  ngOnInit() {
    if (!this.authService.currentUser() && this.authService.isAuthenticated) {
      this.authService.loadCurrentUser();
    }
  }

  openReview(inReview: boolean): void {
    this.shell.emailMenuExpanded.update((expanded) =>
      inReview ? !expanded : true,
    );
  }

  logout() {
    this.authService.logout();
  }
}
