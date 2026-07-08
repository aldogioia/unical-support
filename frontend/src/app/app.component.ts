import { Component, ChangeDetectionStrategy } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { SideNavbarComponent } from './core/layout/side-navbar/side-navbar.component';
import { FeedbackButtonComponent } from './shared/components/feedback-button/feedback-button.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SideNavbarComponent, FeedbackButtonComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AppComponent {
  title = 'unical-support';
}
