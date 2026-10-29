# Análise Python reproduzível

`notebooks/analise.py` e `notebooks/analise.ipynb` consultam o PostgreSQL. Não há leitura de arquivos de vendas, geração de registros nem fallback. Uma falha do banco, ETL incompleto ou recorte vazio encerra a execução antes de criar os gráficos. A conexão vem de `DATABASE_URL`, com padrão local `postgresql://automotive:automotive_local@127.0.0.1:55432/automotive`.

Na raiz do projeto, com as dependências de `requirements.txt` instaladas:

```powershell
python notebooks/analise.py --pais BR --origem real --ano 2025
python notebooks/analise.py --pais GB --origem real --medida first_registrations_including_imports --ano 2025
python -m pytest tests/test_api.py -q
```


## Contrato analítico

- Origem, país e medida são filtros explícitos. Os primeiros registros DfT incluem importados usados; não são combinados com novos registros SMMT/Fenabrave.
- Boxplot consulta a fato e usa P5, P25, mediana, P75 e P95 por segmento. As hastes são P5/P95, não Tukey; as observações não são ponderadas por unidades. Correlação usa pares por modelo: preço médio ponderado por unidades e volume anual; exige ao menos três pares e variância nas duas medidas.
- O mapa usa geometrias e medidas carregadas no PostgreSQL. Prioriza estados com dados; sem dados estaduais, mostra países para a mesma origem/medida/ano. Territórios ausentes ficam cinza, sem zero. É volume absoluto, não taxa per capita; diferentes coberturas reais limitam comparação. Geometrias são representação Natural Earth, sem finalidade cadastral.
- A nuvem usa o volume dos modelos como frequência. A máscara de carro é um desenho geométrico autoral, decorativo e sem conteúdo estatístico; `random_state=42` estabiliza a composição.
- A extrapolação linear exige ao menos três anos completos consecutivos. O backtest usa janelas crescentes a partir de três anos e nunca treina no futuro. MAE ausente significa que não houve ponto temporal suficiente para validação. Não há intervalo probabilístico nem recomendação comercial; mudança de cobertura invalida uma leitura de crescimento de mercado.

## Testes de integração

`tests/test_api.py` usa FastAPI TestClient e o PostgreSQL real. Não há monkeypatch da conexão nem fixtures de vendas. O setup exige ETL concluído e fato não vazia. Os testes conferem ranking e paginação contra SQL independente, estados, separação de métricas, filtros, séries, ausência de alocação estadual real, preços ausentes, geometria, comparação, proveniência, erros 404 e validação 422. São consultas somente leitura; não alteram o banco.
