# Ativos visuais e geográficos verificados

As seis imagens de cidade foram baixadas do Wikimedia Commons, totalizando 2.193.153 bytes. `media.json` contém fonte primária, crédito, licença, link da licença, data da fotografia, data de acesso, hash SHA256, tamanho e dimensões **reais** lidas do JPEG. O endpoint Commons retornou dimensões solicitadas de 1.600 px, mas cinco arquivos servidos têm 1.920 px; a auditoria corrigiu o metadado para o conteúdo efetivamente baixado. Tóquio conserva 1.024×768.

| Arquivo | Local retratado | Autor | Licença |
|---|---|---|---|
| skyline-br.jpg | Centro de São Paulo | Rodrigo.Argenton | CC BY-SA 4.0 |
| skyline-us.jpg | Nova York vista de Nova Jersey | Juliancolton | Domínio público (PD-self) |
| skyline-gb.jpg | Londres ao pôr do sol | lumiDkrof | CC BY-SA 2.0 |
| skyline-de.jpg | Berlim | abbilder | CC BY 2.0 |
| skyline-jp.jpg | Tóquio | Ningyou, atribuído pela página | Domínio público (PD-self) |
| skyline-fr.jpg | Paris vista de Sacré Cœur | bjahind | CC BY-SA 2.0 |

Créditos, licença e link devem permanecer visíveis no aplicativo. As imagens não foram alteradas localmente. O uso com `object-fit: cover` ou como background pode recortar a exibição; identifique esse recorte na atribuição, em especial nas imagens CC BY-SA. A licença da imagem deve continuar preservada e não é convertida na licença do código.

Imagens são representações do local especificado, não prova de nenhuma estatística automotiva. A fotografia de São Paulo pode servir como referência do Brasil, mas **não** deve ser rotulada como foto do Rio de Janeiro ou de outra UF. Se o estado selecionado não tiver foto própria, use fallback identificado como imagem de referência do país e mostre o nome real do local. A mesma regra vale para Nova York ao selecionar outro estado americano.

`local_path` é apenas a localização da coleta no ambiente desta tarefa. Para empacotar de forma portátil, copie `filename` para `web/public/media/` (ou outro diretório de ativos) e grave no banco uma URL servida pelo aplicativo, sem usar os caminhos absolutos da máquina.

## Geografias

Fonte: Natural Earth, repositório oficial mantido por Nathaniel Vaughn Kelso e colaboradores. [Termos primários](https://www.naturalearthdata.com/about/terms-of-use/): todos os dados vetoriais e raster Natural Earth são de domínio público. Crédito sugerido: **Made with Natural Earth**.

- `world.geojson`: 177 feições administrativas, derivadas de `ne_110m_admin_0_countries.geojson`; propriedades reduzidas e identificador ISO da fonte. BR, US, GB, DE, JP e FR ocorrem uma vez cada.
- `states-br-us.geojson`: 78 feições de `ne_50m_admin_1_states_provinces.geojson`, filtradas para as 27 UFs brasileiras e os 50 estados americanos mais Washington, D.C. Os IDs são códigos únicos ISO 3166-2.
- As coordenadas e geometrias das subdivisões foram comparadas ao arquivo original e são exatamente iguais; apenas propriedades e seleção de feições foram alteradas. Não houve desenho ou criação de fronteiras.
- Arquivos originais, metadados, URL, hashes e auditoria estão preservados nesta pasta. `audit.json` registra as verificações executadas.
- Escala cartográfica simplificada adequada à navegação país/estado; não substitui malha de precisão de cadastros ou uso jurídico. As fronteiras seguem a representação da fonte e não constituem declaração sobre disputas territoriais.

## Fotos opcionais de automóveis

`download_cars.py` coleta opcionalmente Polo e Puma e grava `cars.json`. As licenças e páginas foram lidas: Charles/usf1fan2 (Polo, CC BY 2.0) e Alexander-93/Alexander Migl (Puma, CC BY-SA 4.0). Use as legendas fornecidas: a foto é ilustrativa da linha e não confirma a versão, ano-modelo ou mercado do agregado de emplacamentos. Não use como prova de equipamentos ou configuração técnica.
