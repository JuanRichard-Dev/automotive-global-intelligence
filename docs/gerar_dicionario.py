"""Regenera o dicionário a partir do DDL e do schema de entrada, sem acessar serviços."""
from pathlib import Path
import csv
import re

ROOT = Path(__file__).resolve().parents[1]

TABLES = {
    "fonte_dados": "Catálogo de publicação, medida, direitos, cobertura e rastreabilidade",
    "dim_pais": "Países da referência geográfica com identificadores ISO",
    "mapa_base": "Geometrias de representação mundial e vínculo com a fonte geográfica",
    "dim_estado": "Subdivisões de países; códigos ISO e IBGE quando aplicáveis",
    "dim_cidade": "Localidades publicadas pela fonte; vazia enquanto não há cobertura municipal",
    "dim_marca": "Fabricantes normalizados observados na carga",
    "dim_modelo": "Modelo agregado da fonte, vinculado à marca; não identifica cada versão",
    "dim_segmento": "Domínio de carroceria/segmento, incluindo não informado",
    "dim_combustivel": "Domínio de combustível, incluindo desconhecido e outro",
    "dim_tempo": "Referência de período; sua data não equivale a dia individual de venda",
    "dim_medida": "Definição da métrica, sem equivalência presumida entre registros e vendas",
    "midia": "Mídia licenciada, crédito, localização representada e vínculo de modelo/território",
    "cambio": "Taxa de referência para converter moeda original em USD, com data e fonte",
    "fato_vendas": "Observação real publicada na granularidade da fonte",
    "fato_mercado": "Denominador publicado e compatível com o universo de uma consulta",
    "app_config": "Configuração e conteúdo textual exibidos a partir do banco",
    "execucao_etl": "Registro da execução real, hashes de entrada e relatório de qualidade",
}

DESCRIPTIONS = {
    "id": "Identificador da entidade nesta tabela; não é VIN nem dado pessoal de proprietário",
    "ano": "Ano de referência da observação ou dimensão temporal",
    "registro_id": "Identificador do registro canônico real; chave composta com ano na fato",
    "pais_id": "País efetivamente observado, chave para dim_pais",
    "estado_id": "Subdivisão efetivamente informada; nula quando a fonte só sustenta o país",
    "cidade_id": "Localidade informada pela fonte; nula na ausência de cobertura municipal",
    "marca_id": "Fabricante normalizado, chave para dim_marca",
    "modelo_id": "Nome agregado do modelo na fonte; não permite transferir dados entre versões",
    "segmento_id": "Categoria observada ou não informado, sem inferência pelo nome do carro",
    "combustivel_id": "Combustível observado ou categoria desconhecida/outro",
    "tempo_id": "Período representativo em dim_tempo; não é data individual de transação",
    "fonte_id": "Publicação responsável por sustentar o registro; FK para fonte_dados",
    "origem": "real; única origem aceita para novos fatos",
    "medida": "Definição da contagem; registros novos e primeiros registros com importações são distintos",
    "periodicidade": "anual, mensal ou trimestral; consultar uma granularidade por vez",
    "mes": "Mês observado/final do trimestre; nulo para agregado anual",
    "unidades": "Volume medido na granularidade e no universo da fonte; distinto do número de linhas",
    "preco_original": "Valor publicado na moeda declarada; nulo quando não observado",
    "moeda_original": "Moeda ISO4217 da observação de preço",
    "cambio_usd": "USD por unidade da moeda original na data-base registrada",
    "preco_usd": "Preço original multiplicado pelo câmbio de referência; não é preço real inventado",
    "data_cambio": "Data da taxa de referência aplicada, não necessariamente data histórica da observação",
    "registro_origem": "Localizador rastreável da publicação e linha canônica real",
    "hash_origem": "SHA256 ou hash preservado de origem; verificar a semântica de cada conector",
    "coletado_em": "Data de coleta/execução declarada pelo produtor do registro",
    "observacao": "Condições e limites relevantes da interpretação do registro ou da mídia",
    "organizacao": "Organização responsável pela fonte ou publicação",
    "titulo": "Título da publicação ou da mídia conforme o catálogo",
    "url": "URL de origem da fonte ou caminho servido da mídia",
    "ano_inicio": "Primeiro ano de cobertura confirmado no catálogo; nulo se só houve pesquisa de disponibilidade",
    "ano_fim": "Último ano de cobertura confirmado no catálogo; não implica ano completo",
    "licenca": "Licença ou restrição efetivamente identificada; não herda a licença do código",
    "licenca_url": "Página oficial da licença ou termos aplicáveis à fonte/mídia",
    "acesso_em": "Data de acesso registrada na pesquisa da publicação",
    "tipo": "Natureza da fonte, mídia ou localidade conforme seu domínio",
    "cobertura": "Universo, geografia, abrangência, categorias e períodos sustentados pela fonte",
    "limitacoes": "Lacunas e condições que impedem generalização ou comparação direta",
    "sha256": "SHA256 do arquivo consultado quando disponível",
    "status": "Estado efetivo de pesquisa/coleta ou execução; consultada não significa carregada",
    "iso": "Código de país ISO3166-1 alpha2, sem inventar cobertura de dados",
    "iso3": "Código alpha3 preservado da referência geográfica, quando publicado",
    "nome": "Nome descritivo da entidade nesta dimensão",
    "continente": "Agrupamento geográfico da referência Natural Earth",
    "geometria": "GeoJSON da fonte cartográfica, sem valores automotivos fixos no navegador",
    "codigo": "Código do domínio/subdivisão conforme a entidade; estado usa ISO3166-2",
    "sigla": "Sigla postal da subdivisão, vinculada ao país para evitar ambiguidades",
    "codigo_ibge": "Código IBGE da UF brasileira; nulo para subdivisões de outros países",
    "chave": "Hash/chave única da entidade ou nome da configuração no banco",
    "data_iso": "Data representativa do período, em ISO; não dia comprovado de uma venda",
    "trimestre": "Número do trimestre civil derivado do mês, de1 a4",
    "mes_nome": "Nome em português do mês de referência",
    "definicao": "Definição operacional da medida; usada para impedir falsas equivalências",
    "lugar": "Local realmente retratado na imagem, sem confundir fallback nacional e estado",
    "credito": "Atribuição visível exigida pela licença da imagem",
    "origem_url": "Página primária da mídia, com autoria/licença verificáveis",
    "largura": "Largura real do arquivo de imagem consultado",
    "altura": "Altura real do arquivo de imagem consultado",
    "blur_data_url": "Placeholder de pré-carregamento derivado da imagem; não é dado analítico",
    "moeda": "Código monetário ISO4217 da taxa de referência",
    "data_referencia": "Data-base da taxa/medição, distinta da data de acesso",
    "usd_por_unidade": "Valor de uma unidade monetária em USD, publicado/derivado da referência BCE",
    "valor": "Configuração JSON consultada pela aplicação, não uma semente numérica no front-end",
    "iniciada_em": "Instante UTC de início da execução ETL",
    "terminada_em": "Instante UTC de conclusão ou falha da execução",
    "seed": "Campo técnico legado; novas execuções reais gravam zero, sem geração",
    "linhas_sinteticas": "Campo técnico legado; novas execuções reais gravam zero",
    "qualidade": "Relatório JSON de recebidos, rejeições, revisão, duplicidades, tratados e reconciliação",
    "record_id": "Identificador canônico de entrada, convertido para registro_id na fato",
    "country_iso": "País ISO da linha de entrada; parte do particionamento Parquet",
    "state_code": "Código de subdivisão, como BR-SP ou US-CA; não inferido do total nacional",
    "city": "Código de localidade publicado; nulo sem cobertura municipal",
    "year": "Ano publicado, normalizado para ano",
    "month": "Mês de referência/fim do trimestre; ausente em anual real",
    "period_kind": "annual, monthly ou quarterly na entrada; normalizado sem interpolar meses",
    "brand": "Fabricante original/canônico antes do alias explícito aplicado no Spark",
    "model": "Modelo agregado publicado; sem fusão aproximada de variantes de nomes",
    "segment": "Segmento observado; permanece desconhecido quando a fonte não o publica",
    "fuel": "Combustível observado ou não informado; não inferido só do modelo",
    "price": "Preço original publicado quando observado; nulo se ausente",
    "currency": "Moeda ISO da observação de preço, não inferida quando ausente",
    "units": "Volume canônico da observação; distinto de count(*)",
    "metric": "Métrica operacional da fonte; mapeada a dim_medida",
    "source_id": "Identificador da publicação que sustenta a linha",
    "origin": "real; qualquer outra origem é rejeitada",
    "reference_period": "Rótulo do período original para auditoria da granularidade",
    "record_origin": "Referência rastreável à linha da publicação de origem",
    "hash_origin": "Hash preservado do arquivo ou registro de origem",
    "collected_at": "Data de coleta ou execução declarada pelo produtor da linha",
}


def columns(body):
    """Separa campos respeitando vírgulas em numeric(), CHECK e expressões."""
    result = []
    start = depth = 0
    quoted = False
    for i, char in enumerate(body):
        if char == "'":
            quoted = not quoted
        if not quoted:
            depth += (char == "(") - (char == ")")
            if char == "," and depth == 0:
                result.append(body[start:i].strip())
                start = i + 1
    result.append(body[start:].strip())
    return result


def unit(name):
    if name in {"preco_usd", "preco_medio_usd"}:
        return "USD"
    if name in {"preco_original", "price"}:
        return "moeda declarada em campo próprio"
    if name in {"usd_por_unidade", "cambio_usd"}:
        return "USD/unidade monetária"
    if name in {"unidades", "units"}:
        return "unidades da métrica declarada"
    if name in {"linhas_sinteticas", "observacoes"}:
        return "observações"
    if name in {"largura", "altura"}:
        return "pixels"
    return "não aplicável"


def generate():
    sql = (ROOT / "db/001_schema.sql").read_text(encoding="utf-8")
    rows = []
    for match in re.finditer(r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\)\s*(?:PARTITION BY RANGE\s*\([^)]*\)\s*)?;", sql, re.S):
        table, body = match.groups()
        pk = set()
        for key in re.findall(r"PRIMARY KEY\s*\(([^)]+)\)", body, re.I):
            pk.update(c.strip() for c in key.split(","))
        refs = {}
        for local, target, remote in re.findall(r"FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)", body, re.I):
            for a, b in zip(local.split(","), remote.split(",")):
                refs[a.strip()] = target + "." + b.strip()
        for definition in columns(body):
            field = re.match(r"^(\w+)\s+(.+)$", definition, re.S)
            if not field or field[1].upper() in {"PRIMARY", "FOREIGN", "CHECK", "UNIQUE", "CONSTRAINT"}:
                continue
            name, tail = field.groups()
            dtype = re.split(r"\s+(?:NOT|NULL|PRIMARY|REFERENCES|UNIQUE|CHECK|DEFAULT)\b", tail, maxsplit=1, flags=re.I)[0].strip()
            primary = name in pk or "PRIMARY KEY" in tail.upper()
            ref = re.search(r"REFERENCES\s+(\w+)\s*\(([^)]+)\)", tail, re.I)
            reference = ref[1] + "." + ref[2] if ref else refs.get(name, "")
            rules = []
            if primary:
                rules.append("chave primária" + (" composta com " + ",".join(sorted(pk)) if len(pk) > 1 else ""))
            if reference:
                rules.append("FK: " + reference)
            if "NOT NULL" in tail.upper() or primary:
                rules.append("obrigatório")
            if "CHECK" in tail.upper():
                rules.append("CHECK documentado no DDL")
            if "UNIQUE" in tail.upper():
                rules.append("valor único")
            rows.append(dict(tabela=table,finalidade_tabela=TABLES.get(table,""),campo=name,tipo_postgresql=dtype,
                             obrigatorio="sim" if "NOT NULL" in tail.upper() or primary else "não",unidade=unit(name),
                             descricao=DESCRIPTIONS.get(name,name.replace("_"," ").capitalize()+" conforme a entidade"),
                             integridade="; ".join(rules) or "tipo e contrato do produtor",
                             ausentes="NULL significa desconhecido/não aplicável; não imputar zero quando não observado",
                             comparabilidade="Manter origem, medida, território, período, fonte e granularidade compatíveis"))
    transform = (ROOT / "etl/transforms.py").read_text(encoding="utf-8").split("def normalize",1)[0]
    for name, kind in re.findall(r"\('([^']+)',T\.([A-Za-z]+)\(\)\)", transform):
        rows.append(dict(tabela="entrada_RAW_SCHEMA",finalidade_tabela="Contrato explícito da entrada do ETL antes da promoção à fato",campo=name,tipo_postgresql="Spark "+kind,
                         obrigatorio="validado pelo ETL conforme natureza do campo",unidade=unit(name),descricao=DESCRIPTIONS.get(name,name.replace("_"," ").capitalize()),
                         integridade="etl/transforms.py: normalize e validate",ausentes="Nulos legítimos preservados; inválidos encaminhados para rejeição/revisão",
                         comparabilidade="Somente origem real; não combinar métricas ou granularidades"))
    if not rows or not any(row["tabela"] == "fato_vendas" for row in rows):
        raise ValueError("DDL não reconhecido; o dicionário não foi produzido")
    output = ROOT / "docs/dicionario_dados.csv"
    with output.open("w",encoding="utf-8-sig",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Dicionário gerado: {len(rows)} campos; {len(set(r['tabela'] for r in rows))} contratos/tabelas.")
    return output


if __name__ == "__main__":
    generate()
