import { Component, ChangeDetectionStrategy } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import { LabelIcon, Mail01Icon, NoteIcon, File02Icon } from '@hugeicons/core-free-icons';
import { SettingsService } from './core/services/settings.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, HugeiconsIconComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css', '../../public/styles/input.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  protected readonly LabelIcon = LabelIcon;
  protected readonly Mail01Icon = Mail01Icon;
  protected readonly NoteIcon = NoteIcon;
  protected readonly File02Icon = File02Icon;

  constructor(protected settingsService: SettingsService) {}
}
