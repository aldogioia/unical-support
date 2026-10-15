import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  output,
} from '@angular/core';
import { DsIconComponent } from '../ds-icon/ds-icon.component';
import { ShellUiService } from '../../../core/services/shell-ui.service';

@Component({
  selector: 'app-workspace-header',
  standalone: true,
  imports: [DsIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: ` <header class="workspace-topbar">
    <button
      type="button"
      class="icon-btn navigation-toggle"
      aria-label="Apri o comprimi navigazione"
      [attr.aria-expanded]="
        shell.narrow() ? shell.mobileOpen() : !shell.collapsed()
      "
      (click)="shell.toggleNavigation()"
    >
      <ds-icon name="menu" />
    </button>
    <div class="workspace-title">
      <h1>{{ title() }}</h1>
      <span>{{ subtitle() }}</span>
    </div>
    <div class="workspace-topbar-actions">
      @if (searchable()) {
        <label class="section-search"
          ><ds-icon name="search" /><input
            type="search"
            [attr.aria-label]="'Cerca in ' + title()"
            [placeholder]="placeholder()"
            [value]="search()"
            (input)="searchChange.emit($any($event.target).value)"
          />
          @if (search()) {
            <button
              type="button"
              class="search-clear"
              aria-label="Cancella ricerca"
              (click)="searchChange.emit('')"
            >
              <ds-icon name="close" />
            </button>
          }
        </label>
      }
      <ng-content />
      @if (actionLabel()) {
        <button
          type="button"
          class="btn btn-primary header-primary"
          [disabled]="busy()"
          [attr.aria-busy]="busy()"
          [attr.aria-label]="busy() ? busyLabel() : actionLabel()"
          [title]="busy() ? busyLabel() : actionLabel()"
          (click)="action.emit()"
        >
          @if (busy()) {
            <span class="spinner" aria-hidden="true"></span>
          } @else {
            <ds-icon [name]="actionIcon()" />
          }
          <span>{{ busy() ? busyLabel() : actionLabel() }}</span>
        </button>
      }
    </div>
  </header>`,
})
export class WorkspaceHeaderComponent {
  readonly shell = inject(ShellUiService);
  readonly title = input.required<string>();
  readonly subtitle = input('');
  readonly searchable = input(true);
  readonly search = input('');
  readonly placeholder = input('Cerca…');
  readonly actionLabel = input('');
  readonly actionIcon = input('plus');
  readonly busy = input(false);
  readonly busyLabel = input('In corso…');
  readonly searchChange = output<string>();
  readonly action = output<void>();
}
