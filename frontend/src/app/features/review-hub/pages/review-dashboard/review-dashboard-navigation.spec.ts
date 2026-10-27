import { emailPage } from './review-test-data';
import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { Api } from '../../../../core/api/api';
import { readEmailPageApiEmailsPageGet } from '../../../../core/api/fn/emails/read-email-page-api-emails-page-get';
import { AuthService } from '../../../../core/services/auth.service';
import { ShellUiService } from '../../../../core/services/shell-ui.service';
import { SideNavbarComponent } from '../../../../core/layout/side-navbar/side-navbar.component';
import { ReviewDashboardComponent } from './review-dashboard.component';

@Component({ standalone: true, template: '' })
class OtherPage {}

const email = {
  id: 'email-1',
  gmail_id: 'gmail-1',
  sender: 'student@example.org',
  subject: 'Domanda',
  body: 'Informazioni',
  status: 'DRAFT' as const,
  generated_draft: 'Bozza',
  categories: [],
};

describe('Email filters in sidebar navigation', () => {
  let api: jasmine.SpyObj<Api>;
  beforeEach(async () => {
    api = jasmine.createSpyObj<Api>('Api', ['invoke']);
    api.invoke.and.returnValue(Promise.resolve(emailPage([email])) as any);
    await TestBed.configureTestingModule({
      imports: [SideNavbarComponent],
      providers: [
        provideRouter([
          { path: 'review', component: ReviewDashboardComponent },
          { path: 'review-hub', redirectTo: 'review', pathMatch: 'full' },
          { path: 'other', component: OtherPage },
        ]),
        { provide: Api, useValue: api },
        {
          provide: AuthService,
          useValue: { isAuthenticated: false, currentUser: signal(null) },
        },
      ],
    }).compileComponents();
  });
  it('opens a deep-linked status without adding an initial request for the default filter', async () => {
    const harness = await RouterTestingHarness.create();
    const page = await harness.navigateByUrl(
      '/review-hub?status=SENT',
      ReviewDashboardComponent,
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    harness.detectChanges();
    expect(page.selectedStatus()).toBe('SENT');
    expect(api.invoke.calls.count()).toBe(1);
    expect(api.invoke).toHaveBeenCalledWith(readEmailPageApiEmailsPageGet, {
      status: 'SENT', limit: 50,
    });
    expect(
      harness.routeNativeElement!.querySelector('.workspace-toolbar'),
    ).toBeNull();
    harness.fixture.destroy();
  });
  it('uses sidebar links to change the same page and shares its loaded counters', async () => {
    const harness = await RouterTestingHarness.create(
      '/review-hub?status=DRAFT',
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    const sidebar = TestBed.createComponent(SideNavbarComponent);
    sidebar.detectChanges();
    await new Promise((resolve) => setTimeout(resolve, 0));
    sidebar.detectChanges();
    const links = Array.from(
      sidebar.nativeElement.querySelectorAll('.email-submenu a'),
    ) as HTMLAnchorElement[];
    expect(
      links.map((link) =>
        [
          link.querySelector('span:not(.submenu-dot)')!.textContent!.trim(),
          link.querySelector('small')!.textContent!.trim(),
        ].join(' '),
      ),
    ).toEqual([
      'Bozze 1',
      'Da gestire 0',
      'In elaborazione 0',
      'Errori 0',
      'Inviate 0',
    ]);
    sidebar.nativeElement.querySelector('.email-navigation a').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
    harness.detectChanges();
    sidebar.detectChanges();
    expect(TestBed.inject(Router).url).toBe('/review?status=ALL');
    expect(TestBed.inject(ShellUiService).emailStatus()).toBe('ALL');
    expect(api.invoke).toHaveBeenCalledWith(readEmailPageApiEmailsPageGet, { limit: 50 });
    expect(sidebar.nativeElement.querySelector('.sub-current')).toBeNull();
    expect(sidebar.componentInstance.shell.emailMenuExpanded()).toBeFalse();
    sidebar.nativeElement.querySelector('.email-menu-toggle').click();
    sidebar.detectChanges();
    expect(sidebar.componentInstance.shell.emailMenuExpanded()).toBeTrue();
    expect(sidebar.nativeElement.textContent).not.toContain(
      'Segreteria studenti',
    );
    expect(
      sidebar.nativeElement.querySelector('a[href="/design-system"]'),
    ).toBeNull();
    sidebar.destroy();
    harness.fixture.destroy();
  });
  it('restores the URL and selection when a filter change would discard edited text', async () => {
    const harness = await RouterTestingHarness.create();
    const page = await harness.navigateByUrl(
      '/review-hub?status=DRAFT',
      ReviewDashboardComponent,
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    page.selectEmail(email);
    page.editableDraft.set('Modifiche da conservare');
    spyOn(window, 'confirm').and.returnValue(false);
    await TestBed.inject(Router).navigateByUrl('/review?status=ALL');
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(TestBed.inject(Router).url).toBe('/review?status=DRAFT');
    expect(page.selectedStatus()).toBe('DRAFT');
    expect(page.editableDraft()).toBe('Modifiche da conservare');
    harness.fixture.destroy();
  });
  it('opens all email and expands the menu when entering from another section', async () => {
    const harness = await RouterTestingHarness.create('/other');
    const sidebar = TestBed.createComponent(SideNavbarComponent);
    sidebar.componentInstance.shell.emailMenuExpanded.set(false);
    sidebar.detectChanges();
    sidebar.nativeElement.querySelector('.email-navigation a').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    harness.detectChanges();
    sidebar.detectChanges();
    expect(TestBed.inject(Router).url).toBe('/review?status=ALL');
    expect(sidebar.componentInstance.shell.emailMenuExpanded()).toBeTrue();
    expect(
      sidebar.nativeElement.querySelectorAll('.email-submenu a').length,
    ).toBe(5);
    expect(
      sidebar.nativeElement.querySelector('.email-navigation a.active'),
    ).not.toBeNull();
    sidebar.nativeElement.querySelector('.email-submenu a').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    harness.detectChanges();
    sidebar.detectChanges();
    expect(
      sidebar.nativeElement.querySelector('.sub-current').textContent,
    ).toContain('Bozze');
    expect(
      sidebar.nativeElement.querySelector('.email-navigation a.active'),
    ).not.toBeNull();
    sidebar.destroy();
    harness.fixture.destroy();
  });
});
