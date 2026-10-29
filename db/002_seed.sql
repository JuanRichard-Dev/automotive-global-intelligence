INSERT INTO dim_segmento VALUES
(0,'nao_informado','Não informado'),(1,'suv','SUV'),(2,'sedan','Sedã'),(3,'hatch','Hatch'),(4,'picape','Picape')
ON CONFLICT(id) DO NOTHING;
INSERT INTO dim_combustivel VALUES
(0,'nao_informado','Não informado'),(1,'gasolina','Gasolina'),(2,'flex','Flex'),(3,'diesel','Diesel'),(4,'hibrido','Híbrido'),(5,'eletrico','Elétrico'),(6,'outro','Outro'),(7,'gas','Gás'),(8,'hidrogenio','Hidrogênio')
ON CONFLICT(id) DO NOTHING;
INSERT INTO dim_medida VALUES
('new_registrations','Registros de veículos novos','Emplacamentos/registros de novos conforme a fonte; não são necessariamente vendas efetivas ao consumidor.'),
('first_registrations_including_imports','Primeiros registros, incluindo importados','Primeiro registro no território; a fonte DfT inclui novos e veículos importados, inclusive usados. Não equivale a vendas de novos.')
ON CONFLICT(codigo) DO NOTHING;
INSERT INTO app_config VALUES
('identidade','{"nome":"MOTOR ATLAS","assinatura":"Automotive Intelligence","titulo":"A geografia da preferência automotiva.","descricao":"Explore os modelos que lideram os registros, país por país. Evidências publicadas, com fonte e medida explícitas."}'),
('padrao','{"pais":"BR","ano":2025,"origem":"real","medida":"new_registrations","periodicidade":"anual"}'),
('metodologia','{"titulo":"A evidência vem antes do ranking.","regras":["Registros, primeiros registros e vendas não são medidas intercambiáveis.","Brasil: top 50 de automóveis por informe; a participação usa o total do mercado elegível.","Reino Unido: DfT mede primeiros registros, incluindo veículos usados importados.","Fontes nacionais não foram distribuídas artificialmente entre estados ou cidades.","Preços e segmentos ausentes permanecem desconhecidos.","Fotos são ilustrativas; a versão e o mercado da imagem podem diferir do agregado."]}'),
('origens','[{"codigo":"real","nome":"Evidência real","descricao":"Registros publicados por fontes identificadas"}]')
ON CONFLICT(chave) DO UPDATE SET valor=EXCLUDED.valor;
