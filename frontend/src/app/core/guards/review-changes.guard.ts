import { CanDeactivateFn } from '@angular/router';

export const reviewChangesGuard: CanDeactivateFn<{ canLeave(): boolean }> = component => component.canLeave();
