# CSS frameworks embarcados

Estilos downloaded localmente para o app funcionar sem CDN (servidos em `/css/frameworks/*`).

| Framework | Arquivo | Versão | Origem | Licença |
|---|---|---|---|---|
| Bootstrap | `bootstrap@5.3.8.min.css` | 5.3.8 | https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css | MIT |
| Bulma | `bulma@1.0.2.min.css` | 1.0.2 | https://cdn.jsdelivr.net/npm/bulma@1.0.2/css/bulma.min.css | MIT |
| DaisyUI | `daisyui@5.6.8.min.css` | 5.6.8 | https://cdnjs.cloudflare.com/ajax/libs/daisyui/5.6.8/daisyui.css | MIT |
| DaisyUI themes | `daisyui@5.6.8.themes.min.css` | 5.6.8 | https://cdnjs.cloudflare.com/ajax/libs/daisyui/5.6.8/themes.min.css | MIT |
| Pico CSS | `pico@2.min.css` | 2.x | https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css | MIT |
| Picnic CSS | `picnic@7.1.0.min.css` | 7.1.0 | https://cdn.jsdelivr.net/npm/picnic@7.1.0/picnic.min.css | MIT |

## Como usar

Todo framework é servido localmente pelo módulo `mod_intranet/tema_css.py`. A injeção é
por página (evita conflito de resets com o Quasar/Tailwind do NiceGUI):

```python
from mod_intranet import tema_css

tema_css.injetar_framework("bulma")   # adiciona <link> ao <head> da página atual
```

Lista de frameworks: `tema_css.FRAMEWORKS_CSS` (nome -> descrição + aviso de compatibilidade).

## Avaliação de compatibilidade

- **Bootstrap**: grid `.row`/`.col-*` + componentes `.btn`, `.card`, `.badge`, `.table`.
  Reset global (box-sizing, headings, body) pode afetar o Quasar — injetar por página em
  telas de marca própria. Somente o CSS está embarcado; componentes com JS (dropdown,
  offcanvas, toast, carousel) não funcionam sem o bundle.
- **Bulma**: component-based sobre flexbox; classe `.button` e resets podem colidir com o
  Quasar. Seguro em páginas com componentes próprios.
- **DaisyUI**: componentes sobre Tailwind (`.btn`, `.card`, `.badge`); utilitários de cor v2+
  podem conflitar com o Tailwind v3 embutido. Uso por página.
- **Pico**: reset sem classes — estiliza elementos nativos; só com injeção escopada.
- **Picnic**: leve, mas manutenção reduzida; ideal para telas independentes.

## Atualização

Baixar nova versão com `curl` e ajustar o nome do arquivo em `FRAMEWORKS_CSS`
(`mod_intranet/tema_css.py`).