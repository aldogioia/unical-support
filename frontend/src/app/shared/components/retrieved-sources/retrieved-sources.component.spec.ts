import { TestBed } from '@angular/core/testing';
import { RetrievedSourcesComponent } from './retrieved-sources.component';

describe('Fonti recuperate', () => {
  async function render(sources?: any) {
    await TestBed.configureTestingModule({ imports: [RetrievedSourcesComponent] }).compileComponents();
    const fixture = TestBed.createComponent(RetrievedSourcesComponent);
    if (sources !== undefined) fixture.componentRef.setInput('sources', sources);
    fixture.detectChanges();
    return fixture;
  }
  it('distinguishes an old draft from an empty recorded search', async () => {
    const fixture = await render(null);
    expect(fixture.nativeElement.textContent).toContain('Non registrate');
    fixture.componentRef.setInput('sources', []); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nessuna fonte trovata');
    expect(fixture.nativeElement.textContent).not.toContain('Non registrate');
  });
  it('groups actual passages by document and renders its public link', async () => {
    const source = {document_id:'doc-1', source_name:'Guida', reference_url:'https://example.org/guida', page:'2', excerpt:'Primo frammento'};
    const fixture = await render([source, {...source, page:'3', excerpt:'Secondo frammento'}]);
    expect(fixture.nativeElement.querySelectorAll('article').length).toBe(1);
    expect(fixture.nativeElement.querySelectorAll('blockquote').length).toBe(2);
    expect(fixture.nativeElement.textContent).toContain('1 documento');
    expect(fixture.nativeElement.querySelector('a').href).toBe('https://example.org/guida');
    expect(fixture.nativeElement.querySelector('a').rel).toContain('noopener');
    expect(fixture.nativeElement.textContent).toContain('Pagina 3');
    expect(fixture.nativeElement.textContent).not.toContain('AI confidence');
  });
  it('shows unlinked sources and treats retrieved markup as text', async () => {
    const fixture = await render([{source_name:'Manuale interno', reference_url:null, excerpt:'<script>alert(1)</script>'}]);
    expect(fixture.nativeElement.textContent).toContain('Link pubblico non disponibile');
    expect(fixture.nativeElement.querySelector('a')).toBeNull();
    expect(fixture.nativeElement.querySelector('script')).toBeNull();
    expect(fixture.nativeElement.querySelector('blockquote').textContent).toContain('<script>');
  });
});
