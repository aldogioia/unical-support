"""Generate an offline preview with the real logo embedded, without sending mail."""
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.email_renderer import render_email, LOGO_CID, LOGO_PATH

body = '''Ciao,

questa è un’anteprima dimostrativa di Unical Support. Il contenuto serve a verificare la leggibilità dell’email e non descrive procedure amministrative reali dell’Ateneo.

La risposta mantiene paragrafi brevi e un tono diretto. Il testo si adatta allo schermo, così da restare leggibile sia sul telefono sia sul computer, senza interruzioni di riga inserite a metà frase.

Ecco come vengono presentati i punti di una risposta:
- Un’informazione essenziale, con spazio sufficiente per leggerla.
- Un riferimento alla fonte: https://example.org/documento-dimostrativo.pdf

Per una procedura in più passaggi:
1. Consulta la fonte indicata nella risposta.
2. Verifica le informazioni prima di procedere.

Un saluto,
Segreteria Unical'''
rendered = render_email(body, 'it')
logo = base64.b64encode(LOGO_PATH.read_bytes()).decode('ascii')
output = Path(sys.argv[1] if len(sys.argv) > 1 else 'docs/assets/email-preview.html')
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(rendered.html.replace(f'cid:{LOGO_CID}', f'data:image/png;base64,{logo}'), encoding='utf-8')
print(output)
