from pathlib import Path
import os
from typing import Annotated
from fastapi import FastAPI,Depends,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from .db import query,cached
from .models import Filters,Page
from .analytics import ranking,resolve,where,series,statistics

ROOT=Path(__file__).resolve().parents[1]
def require_ready():
    # Uma reconstrução da carga não deve expor fatos parcialmente carregados.
    return health()

app=FastAPI(title='Motor Atlas — API de inteligência automotiva',version='1.0.0',description='PostgreSQL como fonte única. Evidências reais com medidas e períodos explícitos.',dependencies=[Depends(require_ready)])
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:3000,http://127.0.0.1:3100').split(','),allow_credentials=False,allow_methods=['GET'],allow_headers=['Content-Type'])
app.mount('/media',StaticFiles(directory=ROOT/'data/media'),name='media')
F=Annotated[Filters,Depends()]
P=Annotated[Page,Depends()]

@app.exception_handler(ValidationError)
async def invalid_filters(request,exc):
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in exc.errors()]})

@app.get('/health')
def health():
    try:
        q=query("SELECT status,qualidade FROM execucao_etl ORDER BY iniciada_em DESC LIMIT 1",one=True)
        if not q or q['status']!='concluida' or (q.get('qualidade') or {}).get('modo')!='real':raise RuntimeError('ETL mais recente ainda não concluído')
        return dict(status='ok',database='postgresql',etl=q['status'])
    except Exception as e:raise HTTPException(503,'Banco/ETL indisponível: '+str(e))

@app.get('/paises')
def countries(pagina:int=Query(1,ge=1),tamanho:int=Query(200,ge=1,le=200)):
    return dict(items=query('''SELECT p.id,p.iso,p.nome,p.continente,
      coalesce(bool_or(a.origem='real'),false) tem_real,
      array_remove(array_agg(DISTINCT a.medida),NULL) medidas
      FROM dim_pais p LEFT JOIN mv_agregados a ON a.pais_id=p.id GROUP BY p.id ORDER BY count(a.pais_id)>0 DESC,p.nome LIMIT %s OFFSET %s''',(tamanho,(pagina-1)*tamanho)),pagina=pagina,tamanho=tamanho)

@app.get('/paises/{iso}/estados')
def states(iso:str):
    if not query('SELECT id FROM dim_pais WHERE iso=%s',(iso,),True):raise HTTPException(404,'País não cadastrado')
    return dict(items=query("SELECT e.id,e.codigo,e.sigla,e.nome FROM dim_estado e JOIN dim_pais p ON p.id=e.pais_id WHERE p.iso=%s AND EXISTS(SELECT 1 FROM fato_vendas f WHERE f.estado_id=e.id AND f.origem='real') ORDER BY e.nome",(iso,)))

@app.get('/paises/{iso}/top-carros')
def country_top(iso:str,f:F,p:P):
    if f.estado:raise HTTPException(422,'Use o endpoint de estado para um recorte estadual')
    f=Filters(**{**f.model_dump(),'pais':iso})
    result=ranking(f,p.tamanho,(p.pagina-1)*p.tamanho);result.update(pagina=p.pagina,tamanho=p.tamanho);return result

@app.get('/estados/{uf}/top-carros')
def state_top(uf:str,f:F,p:P):
    code=uf if '-' in uf else 'BR-'+uf
    state=query('SELECT e.codigo,p.iso FROM dim_estado e JOIN dim_pais p ON p.id=e.pais_id WHERE e.codigo=%s',(code,),True)
    if not state:raise HTTPException(404,'Estado não cadastrado; use o código ISO, por exemplo BR-SP ou US-CA')
    ff=Filters(**{**f.model_dump(),'pais':state['iso'],'estado':state['codigo']})
    result=ranking(ff,p.tamanho,(p.pagina-1)*p.tamanho);result.update(pagina=p.pagina,tamanho=p.tamanho);return result

@app.get('/marcas')
def brands(pagina:int=Query(1,ge=1),tamanho:int=Query(100,ge=1,le=500)):
    return dict(items=query('SELECT id,nome FROM dim_marca ORDER BY nome LIMIT %s OFFSET %s',(tamanho,(pagina-1)*tamanho)),pagina=pagina)

@app.get('/modelos/{id}')
def model(id:int):
    obj=query('SELECT m.id,m.nome,b.nome marca FROM dim_modelo m JOIN dim_marca b ON b.id=m.marca_id WHERE m.id=%s',(id,),True)
    if not obj:raise HTTPException(404,'Modelo não encontrado')
    obj['series']=query('SELECT p.iso,p.nome pais,a.ano,a.origem,a.medida,sum(a.unidades)::bigint unidades FROM mv_agregados a JOIN dim_pais p ON p.id=a.pais_id WHERE a.modelo_id=%s AND periodicidade=%s GROUP BY p.iso,p.nome,a.ano,a.origem,a.medida ORDER BY a.origem,p.iso,a.ano',(id,'anual'))
    obj['midia']=query('SELECT * FROM midia WHERE modelo_id=%s',(id,))
    return obj

@app.get('/series-temporais')
def timeline(f:F,modelo_id:int|None=None,granularidade:str=Query('anual',pattern='^(anual|mensal|trimestral)$')):
    return series(f,modelo_id,granularidade)

@app.get('/nuvem-palavras')
def cloud(f:F,limite:int=Query(60,ge=5,le=100)):
    ff=resolve(f);clause,p=where(ff)
    return dict(items=query('SELECT b.nome||\' \'||m.nome texto,sum(a.unidades)::bigint valor FROM mv_agregados a JOIN dim_modelo m ON m.id=a.modelo_id JOIN dim_marca b ON b.id=a.marca_id WHERE '+clause+' GROUP BY b.nome,m.nome ORDER BY valor DESC LIMIT %s',p+[limite]),filtros=ff.model_dump(),nota='Tamanho ponderado pelas unidades na cobertura do recorte.')

@app.get('/midia')
def images(pais:str|None=None,estado:str|None=None,modelo_id:int|None=None):
    if modelo_id:return dict(items=query('SELECT * FROM midia WHERE modelo_id=%s',(modelo_id,)))
    if estado:return dict(items=query('SELECT m.* FROM midia m LEFT JOIN dim_pais p ON p.id=m.pais_id LEFT JOIN dim_estado e ON e.id=m.estado_id WHERE e.codigo=%s OR (p.iso=%s AND m.tipo=%s) ORDER BY (e.codigo=%s) DESC',(estado,estado.split('-')[0],'country',estado)))
    return dict(items=query('SELECT m.* FROM midia m LEFT JOIN dim_pais p ON p.id=m.pais_id WHERE (%s::text IS NULL OR p.iso=%s) ORDER BY m.id',(pais,pais)))

@app.get('/fontes')
def sources():return dict(items=query("SELECT * FROM fonte_dados WHERE id NOT LIKE 'SYN%' AND tipo<>'sintetica' ORDER BY status,id"))

@app.get('/estatisticas')
def stats(f:F):return statistics(f)

@app.get('/graficos')
def chart_data(f:F):
    ff=resolve(f);clause,params=where(ff)
    fuels=query('SELECT c.nome,sum(a.unidades)::bigint unidades FROM mv_agregados a JOIN dim_combustivel c ON c.id=a.combustivel_id WHERE '+clause+' GROUP BY c.nome ORDER BY unidades DESC',params)
    return dict(ranking=ranking(ff,5000)['items'],fuels=fuels)

@app.get('/mapa')
def geo(f:F,nivel:str=Query('pais',pattern='^(pais|estado)$')):
    ff=resolve(f);clause,p=where(ff.model_copy(update={'estado':None}))
    if nivel=='pais':
        # A medida fica fixa: mapas não somam bases incompatíveis de países diferentes.
        clause=clause.replace('a.pais_id=(SELECT id FROM dim_pais WHERE iso=%s) AND ','');p=p[1:]
        rows=query('''WITH volume AS(SELECT pais_id,sum(unidades)::bigint unidades FROM mv_agregados a WHERE '''+clause+''' GROUP BY pais_id)
          SELECT b.id,b.nome,b.geometria,p.iso,v.unidades FROM mapa_base b LEFT JOIN dim_pais p ON p.id=b.pais_id LEFT JOIN volume v ON v.pais_id=b.pais_id''',p)
        features=[dict(type='Feature',id=r['id'],geometry=r['geometria'],properties=dict(iso=r['iso'],nome=r['nome'],unidades=r['unidades'],tem_dados=r['unidades'] is not None)) for r in rows]
    else:
        rows=query('''WITH volume AS(SELECT estado_id,sum(unidades)::bigint unidades FROM mv_agregados a WHERE '''+clause+''' GROUP BY estado_id)
          SELECT e.id,e.codigo,e.nome,e.geometria,v.unidades FROM dim_estado e JOIN dim_pais p ON p.id=e.pais_id LEFT JOIN volume v ON v.estado_id=e.id WHERE p.iso=%s AND v.unidades IS NOT NULL''',p+[ff.pais])
        features=[dict(type='Feature',id=r['id'],geometry=r['geometria'],properties=dict(iso=ff.pais,estado=r['codigo'],nome=r['nome'],unidades=r['unidades'],tem_dados=r['unidades'] is not None)) for r in rows]
    return dict(type='FeatureCollection',features=features,fonte='Natural Earth — domínio público; limites de representação, não cadastrais',nota='Regiões sem medida compatível permanecem sem valor, nunca zero inventado.')

@app.get('/comparador')
def compare(f:F,isos:str|None=None):
    if isos is None:
        chosen=[r['iso'] for r in query("SELECT p.iso FROM dim_pais p WHERE EXISTS(SELECT 1 FROM mv_agregados a WHERE a.pais_id=p.id AND a.origem='real' AND a.ano=%s AND a.periodicidade=%s) ORDER BY p.nome LIMIT 6",(f.ano,f.periodicidade))]
    else:
        chosen=isos.split(',')
        if len(chosen)>6 or any(len(x)!=2 or not x.isalpha() or not x.isupper() for x in chosen):raise HTTPException(422,'Escolha até seis códigos ISO')
        chosen=list(dict.fromkeys(chosen))
    items=[]
    for iso in chosen:
        country=query('SELECT iso,nome FROM dim_pais WHERE iso=%s',(iso,),True)
        if not country:continue
        ff=resolve(f.model_copy(update={'pais':iso,'estado':None}))
        r=ranking(ff,1)
        metric=query('SELECT nome FROM dim_medida WHERE codigo=%s',(ff.medida,),True)
        items.append(dict(**country,medida=ff.medida,nome_medida=metric['nome'] if metric else ff.medida,lider=r['items'][0] if r['items'] else None,unidades_observadas=r['unidades_observadas'],mercado_elegivel=r['mercado_elegivel'],cobertura_pct=r['cobertura_pct'],disponivel=bool(r['items'])))
    return dict(items=items,nota='Cada cartão descreve um mercado e informa sua própria medida. Métricas diferentes não formam uma comparação numérica; cobertura parcial limita a interpretação.')

@app.get('/bootstrap')
def bootstrap():
    def load():
        config={r['chave']:r['valor'] for r in query('SELECT chave,valor FROM app_config')}
        opts=query('SELECT p.iso,a.origem,a.medida,a.periodicidade,array_agg(DISTINCT ano ORDER BY ano) anos,array_remove(array_agg(DISTINCT mes ORDER BY mes),NULL) meses FROM mv_agregados a JOIN dim_pais p ON p.id=a.pais_id GROUP BY p.iso,a.origem,a.medida,a.periodicidade')
        return dict(config=config,paises=countries(1,200)['items'],disponibilidade=opts,segmentos=query('SELECT codigo,nome FROM dim_segmento ORDER BY id'),combustiveis=query('SELECT codigo,nome FROM dim_combustivel ORDER BY id'),medidas=query('SELECT * FROM dim_medida'),execucao=query("SELECT id,terminada_em,qualidade FROM execucao_etl WHERE status='concluida' ORDER BY terminada_em DESC LIMIT 1",one=True),painel=panel(Filters(**config['padrao'])))
    return cached(('bootstrap',),load)

@app.get('/painel')
def panel(f:F):
    ff=resolve(f)
    def load():
        country=query('SELECT id,iso,nome FROM dim_pais WHERE iso=%s',(ff.pais,),True)
        if not country:raise HTTPException(404,'País não cadastrado')
        state=query('SELECT codigo,nome FROM dim_estado WHERE codigo=%s',(ff.estado,),True) if ff.estado else None
        if ff.estado and not state:raise HTTPException(404,'Estado não cadastrado')
        rank=ranking(ff,10)
        chosen_sources=query('SELECT * FROM fonte_dados WHERE id=ANY(%s)',(rank['fontes'],)) if rank['fontes'] else []
        image=images(pais=ff.pais,estado=ff.estado)['items']
        leader=rank['items'][0] if rank['items'] else None
        car=images(modelo_id=leader['modelo_id'])['items'] if leader else []
        metric=query('SELECT * FROM dim_medida WHERE codigo=%s',(ff.medida,),True)
        return dict(filtros=ff.model_dump(),pais=country,estado=state,status='ok' if leader else 'sem_dados',medida=metric,ranking=rank,estatisticas=statistics(ff) if leader else None,serie=series(ff),nuvem=cloud(ff,60)['items'] if leader else [],midia_pais=next((x for x in image if x['tipo']=='country'),None),midia_carro=car[0] if car else None,fontes=chosen_sources,nota_ausencia='Não há vendas/registros reais compatíveis por este território e período. Não foi feita distribuição artificial de totais nacionais. Consulte outro período ou país com cobertura publicada.' if not leader else None)
    return cached(('panel',tuple(ff.model_dump().items())),load)

