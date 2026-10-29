# Atualização de mercados e galeria

Carga de 29/10/2026: **35.167 observações reais**, em quatro países:

| País | Observações na base | Fonte |
|---|---:|---|
| Brasil | 1.400 | Fenabrave |
| Reino Unido | 33.667 | DfT/DVLA VEH0160 |
| Itália | 50 | UNRAE, ranking anual 2025 |
| Áustria | 50 | Statistik Austria, Tabela 7, 2025 |

Cada linha é um agregado publicado; os períodos e as definições de registro são separados nas consultas. Não são 35.167 transações individuais. Nenhum dado sintético foi carregado.

Itália: total nacional elegível de 1.525.722, com 1.032.928 unidades nos 50 modelos publicados. Áustria: total de 284.978, com 152.867 unidades nos 50 modelos. A participação de cada modelo usa o total compatível; a cobertura do Top 50 fica explícita nos indicadores.

Fontes primárias, URLs, extração e verificação estão em `data/seed/sources.json`, `etl/sources/reviewed_2025_rankings.json` e `data/raw/adicionais/more_countries/verification_report.json`. Copyright das publicações preservado; licença aberta não presumida. PDFs originais não integram o ZIP. Dados italianos foram conferidos no texto do PDF oficial; o PDF austríaco baixado foi conferido contra a extração. Não foi inventado hash do arquivo italiano.

## Interface

- Removidos o bloco Fontes e metodologia e o rodapé mostrado na referência. Créditos das imagens permanecem junto às fotos.
- Galeria horizontal com setas, teclado e gesto de toque, dez modelos por mercado.
- Dez primeiras posições dos quatro mercados com foto: 40/40 posições atendidas, com modelos compartilhados entre países.
- Catálogo de 36 fotos de carros e seis de cidades, com autor, licença, origem, dimensões e blur.
- Novos gráficos: donut por marca, treemap por modelo e barras empilhadas por combustível quando a fonte informa esse campo. Usam o ranking completo carregado para o recorte, sem calcular percentuais sobre apenas os dez modelos do carrossel.
- Tabelas acessíveis e exportação CSV para os novos gráficos.

## Validação

51 testes passaram (API, novos mercados, fotos, reconciliação dos gráficos e PySpark). Build Next.js, TypeScript e ESLint aprovados. Navegador: carrossel passou de posição zero para scroll horizontal, dez imagens presentes no mercado italiano, e seletor oferece os quatro países. Sem erros de console nessa inspeção. Docker e Lighthouse não executados.
