import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { HugeiconsIconComponent } from '@hugeicons/angular';
import Menu01Icon from '@hugeicons/core-free-icons/Menu01Icon';
import ArrowLeft01Icon from '@hugeicons/core-free-icons/ArrowLeft01Icon';
import Add01Icon from '@hugeicons/core-free-icons/Add01Icon';
import Tag01Icon from '@hugeicons/core-free-icons/Tag01Icon';
import Logout01Icon from '@hugeicons/core-free-icons/Logout01Icon';
import Delete02Icon from '@hugeicons/core-free-icons/Delete02Icon';
import LinkSquare01Icon from '@hugeicons/core-free-icons/LinkSquare01Icon';
import Message01Icon from '@hugeicons/core-free-icons/Message01Icon';
import BookOpen01Icon from '@hugeicons/core-free-icons/BookOpen01Icon';
import GridViewIcon from '@hugeicons/core-free-icons/GridViewIcon';
import PaintBoardIcon from '@hugeicons/core-free-icons/PaintBoardIcon';
import Cursor01Icon from '@hugeicons/core-free-icons/Cursor01Icon';
import Settings04Icon from '@hugeicons/core-free-icons/Settings04Icon';
import Mail01Icon from '@hugeicons/core-free-icons/Mail01Icon';
import Layers01Icon from '@hugeicons/core-free-icons/Layers01Icon';
import Search01Icon from '@hugeicons/core-free-icons/Search01Icon';
import ArrowRight01Icon from '@hugeicons/core-free-icons/ArrowRight01Icon';
import ArrowRight02Icon from '@hugeicons/core-free-icons/ArrowRight02Icon';
import ArrowDown01Icon from '@hugeicons/core-free-icons/ArrowDown01Icon';
import Tick02Icon from '@hugeicons/core-free-icons/Tick02Icon';
import Cancel01Icon from '@hugeicons/core-free-icons/Cancel01Icon';
import SparklesIcon from '@hugeicons/core-free-icons/SparklesIcon';
import Upload01Icon from '@hugeicons/core-free-icons/Upload01Icon';
import File01Icon from '@hugeicons/core-free-icons/File01Icon';
import InformationCircleIcon from '@hugeicons/core-free-icons/InformationCircleIcon';
import Alert02Icon from '@hugeicons/core-free-icons/Alert02Icon';
import Copy01Icon from '@hugeicons/core-free-icons/Copy01Icon';
import ViewIcon from '@hugeicons/core-free-icons/ViewIcon';
import CodeIcon from '@hugeicons/core-free-icons/CodeIcon';
import Clock01Icon from '@hugeicons/core-free-icons/Clock01Icon';
import Notification03Icon from '@hugeicons/core-free-icons/Notification03Icon';
import Disability01Icon from '@hugeicons/core-free-icons/Disability01Icon';

const ICONS: Record<string, typeof Menu01Icon> = {
  menu: Menu01Icon, back: ArrowLeft01Icon, plus: Add01Icon, tag: Tag01Icon,
  logout: Logout01Icon, trash: Delete02Icon, external: LinkSquare01Icon,
  message: Message01Icon, book: BookOpen01Icon, grid: GridViewIcon,
  palette: PaintBoardIcon, cursor: Cursor01Icon, sliders: Settings04Icon,
  mail: Mail01Icon, layers: Layers01Icon, search: Search01Icon,
  arrow: ArrowRight01Icon, chevron: ArrowRight02Icon, down: ArrowDown01Icon,
  check: Tick02Icon, close: Cancel01Icon, sparkle: SparklesIcon,
  upload: Upload01Icon, file: File01Icon, info: InformationCircleIcon,
  warning: Alert02Icon, copy: Copy01Icon, eye: ViewIcon, code: CodeIcon,
  clock: Clock01Icon, bell: Notification03Icon, accessibility: Disability01Icon,
};

@Component({
  selector: 'ds-icon', standalone: true, imports: [HugeiconsIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true' },
  template: '<hugeicons-icon [icon]="icon()" [size]="24" [strokeWidth]="1.75" color="currentColor" />',
  styles: [':host{display:inline-flex;width:18px;height:18px;flex-shrink:0;vertical-align:middle}hugeicons-icon{display:flex;width:100%;height:100%}:host ::ng-deep svg{width:100%;height:100%}'],
})
export class DsIconComponent {
  readonly name = input('grid');
  readonly icon = computed(() => ICONS[this.name()] ?? ICONS['grid']);
}
