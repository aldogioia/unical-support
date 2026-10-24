import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Route, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { routes } from '../../app.routes';
import { AuthService } from '../services/auth.service';

@Component({ standalone: true, template: '<p>Route test</p>' })
class RouteTestComponent {}

describe('Protected route authentication', () => {
  let session: { isAuthenticated: boolean };

  beforeEach(() => {
    session = { isAuthenticated: false };
    // Keep production paths, redirects and guards; avoid loading feature APIs in routing tests.
    const testRoutes: Route[] = routes.map(route => {
      if (!route.loadComponent) return route;
      const { loadComponent, ...config } = route;
      return { ...config, component: RouteTestComponent };
    });
    TestBed.configureTestingModule({ providers: [
      provideRouter(testRoutes), { provide: AuthService, useValue: session },
    ] });
  });

  ['/review', '/review-hub', '/taxonomy', '/knowledge-base', '/ai-settings', '/'].forEach(path => {
    it(`redirects an unauthenticated visit to ${path} to login`, async () => {
      const harness = await RouterTestingHarness.create();
      await harness.navigateByUrl(path);
      expect(TestBed.inject(Router).url).toBe('/login');
    });
  });

  it('allows an authenticated operator through the existing review-hub redirect', async () => {
    session.isAuthenticated = true;
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/review-hub');
    expect(TestBed.inject(Router).url).toBe('/review');
  });
});
