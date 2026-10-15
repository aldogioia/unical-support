import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'ds-icon',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path [attr.d]="paths[name()] || paths['grid']" />
  </svg>`,
  styles: [
    ':host{display:inline-flex;width:18px;height:18px;flex-shrink:0;vertical-align:middle}svg{width:100%;height:100%}',
  ],
})
export class DsIconComponent {
  readonly name = input('grid');
  readonly paths: Record<string, string> = {
    menu: 'M4 6h16 M4 12h16 M4 18h16',
    back: 'M19 12H5 M11 6l-6 6 6 6',
    plus: 'M12 5v14 M5 12h14',
    tag: 'M3 3h9l9 9-9 9-9-9z M7 7h.01',
    logout: 'M9 4H4v16h5 M14 7l5 5-5 5 M8 12h11',
    trash: 'M4 7h16 M9 7V3h6v4 M6 7l1 14h10l1-14 M10 11v6 M14 11v6',
    external: 'M14 3h7v7 M21 3L10 14 M10 5H3v16h16v-7',
    message: 'M21 3H3v14h4v4l5-4h9z',
    book: 'M12 5v16 M3 3h5l4 2 4-2h5v16h-5l-4 2-4-2H3z',
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    palette:
      'M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h4a5 5 0 0 0 0-10z M7 8h.01 M12 6h.01 M17 7h.01 M5 13h.01',
    cursor: 'M4 3l6 17 3-7 7-3z M14 14l6 6',
    sliders: 'M4 7h6 M14 7h6 M4 17h10 M18 17h2 M10 4v6 M14 14v6',
    mail: 'M3 5h18v14H3z M3 5l9 7 9-7',
    layers: 'M12 3L2 8l10 5 10-5z M2 12l10 5 10-5 M2 16l10 5 10-5',
    search: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6',
    arrow: 'M5 12h14 M13 6l6 6-6 6',
    chevron: 'M9 5l7 7-7 7',
    down: 'M6 9l6 6 6-6',
    check: 'M5 12l4 4L19 6',
    close: 'M6 6l12 12 M18 6L6 18',
    sparkle:
      'M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z M20 2v4 M18 4h4',
    upload: 'M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6',
    file: 'M14 2H5v20h14V7z M14 2v5h5 M8 12h8 M8 16h6',
    info: 'M12 8h.01 M12 11v6 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',
    warning: 'M12 3L2 21h20z M12 9v5 M12 17h.01',
    copy: 'M9 9h12v12H9z M15 9V3H3v12h6',
    eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
    code: 'M8 6l-6 6 6 6 M16 6l6 6-6 6 M14 3l-4 18',
    clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20 M12 6v6l4 2',
    bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4',
    accessibility:
      'M12 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4 M4 8l8 2 8-2 M12 10v5 M8 22l4-7 4 7',
  };
}
