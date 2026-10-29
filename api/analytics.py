import numpy as np
from .db import query,cached
from .models import Filters

def resolve(f:Filters):
    if f.medida:return f
    r=query("SELECT medida FROM mv_agregados a JOIN dim_pais p ON p.id=a.pais_id WHERE p.iso=%s AND a.origem=%s ORDER BY CASE WHEN medida='new_registrations' THEN 0 ELSE 1 END LIMIT 1",(f.pais,f.origem),True)
    return f.model_copy(update={'medida':r['medida'] if r else 'new_registrations'})

def where(f,alias='a',year=True):
    parts=[f'{alias}.pais_id=(SELECT id FROM dim_pais WHERE iso=%s)',f'{alias}.origem=%s',f'{alias}.medida=%s',f'{alias}.periodicidade=%s']
    params=[f.pais,f.origem,f.medida,f.periodicidade]
    if year:parts.append(f'{alias}.ano=%s');params.append(f.ano)
    if f.periodicidade!='anual':parts.append(f'{alias}.mes=%s');params.append(f.mes)
    if f.estado:parts.append(f'{alias}.estado_id=(SELECT id FROM dim_estado WHERE codigo=%s)');params.append(f.estado)
    if f.cidade:parts.append(f'{alias}.cidade_id=(SELECT id FROM dim_cidade WHERE codigo=%s)');params.append(f.cidade)
    if f.segmento:parts.append(f'{alias}.segmento_id=(SELECT id FROM dim_segmento WHERE codigo=%s)');params.append(f.segmento)
    if f.combustivel:parts.append(f'{alias}.combustivel_id=(SELECT id FROM dim_combustivel WHERE codigo=%s)');params.append(f.combustivel)
    return ' AND '.join(parts),params

def denominator(f,total_observed):
    if f.estado or (f.segmento and f.segmento!='nao_informado'):return None,'denominador compatível não publicado'
    parts=['pais_id=(SELECT id FROM dim_pais WHERE iso=%s)','ano=%s','origem=%s','medida=%s','periodicidade=%s','estado_id IS NULL']
    params=[f.pais,f.ano,f.origem,f.medida,f.periodicidade]
    if f.mes:parts.append('mes=%s');params.append(f.mes)
    else:parts.append('mes IS NULL')
    if f.combustivel and f.combustivel!='nao_informado':parts.append('combustivel_id=(SELECT id FROM dim_combustivel WHERE codigo=%s)');params.append(f.combustivel)
    else:parts.append('combustivel_id IS NULL')
    r=query('SELECT sum(unidades)::bigint total,count(*) n FROM fato_mercado WHERE '+' AND '.join(parts),params,True)
    if r and r['total'] is not None and r['n']==1 and r['total']>=total_observed:return r['total'],'total publicado para o mesmo universo, período e medida'
    return None,'denominador ausente, duplicado ou incompatível; participação indisponível'

def ranking(f:Filters,limit=10,offset=0):
    f=resolve(f);key=('rank',tuple(f.model_dump().items()),limit,offset)
    def load():
        clause,p=where(f)
        totals=query('SELECT sum(unidades)::bigint unidades,sum(observacoes)::bigint observacoes,count(DISTINCT modelo_id) modelos FROM mv_agregados a WHERE '+clause,p,True)
        observed=totals['unidades'] or 0
        den,method=denominator(f,observed)
        rows=query('''WITH modelos AS (
          SELECT modelo_id,marca_id,sum(unidades)::bigint unidades,sum(receita_usd)/nullif(sum(unidades_com_preco),0) preco_medio_usd
          FROM mv_agregados a WHERE '''+clause+''' GROUP BY modelo_id,marca_id
        ), classificados AS (
          SELECT q.*,m.nome modelo,b.nome marca,row_number() OVER(ORDER BY unidades DESC,b.nome,m.nome) posicao,count(*) OVER() total_modelos
          FROM modelos q JOIN dim_modelo m ON m.id=q.modelo_id JOIN dim_marca b ON b.id=q.marca_id
        ) SELECT * FROM classificados ORDER BY posicao LIMIT %s OFFSET %s''',p+[limit,offset])
        sourceids=query('SELECT DISTINCT unnest(fontes) id FROM mv_agregados a WHERE '+clause,p)
        for r in rows:r['participacao_pct']=r['unidades']/den*100 if den else None
        return dict(items=rows,total=totals['modelos'] or 0,unidades_observadas=observed if rows else None,observacoes=totals['observacoes'] or 0,mercado_elegivel=den,metodo_participacao=method,fontes=[r['id'] for r in sourceids],filtros=f.model_dump(),cobertura_pct=observed/den*100 if den else None)
    return cached(key,load)

def series(f:Filters,modelo_id=None,grain='anual'):
    f=resolve(f).model_copy(update={'periodicidade':grain,'mes':None})
    clause,p=where(f,year=False)
    # Séries percorrem todos os meses/trimestres publicados, sem fixar um mês no WHERE.
    if grain!='anual':
        clause=clause.replace(' AND a.mes=%s','')
        # where recebeu mes=None e incluiu seu placeholder na quinta posição.
        p.pop(4)
    if modelo_id:clause+=' AND a.modelo_id=%s';p.append(modelo_id)
    rows=query('SELECT ano,mes,sum(unidades)::bigint unidades FROM mv_agregados a WHERE '+clause+' GROUP BY ano,mes ORDER BY ano,mes',p)
    forecast=None
    return dict(items=rows,periodicidade=grain,previsao=forecast,nota='Meses, trimestres e anos não são somados entre si. Ausência em top N não é zero; não há interpolação de lacunas.')

def statistics(f):
    f=resolve(f);clause,p=where(f)
    rows=query('''SELECT s.nome segmento,sum(unidades)::bigint unidades FROM mv_agregados a JOIN dim_segmento s ON s.id=a.segmento_id WHERE '''+clause+' GROUP BY s.nome ORDER BY unidades DESC',p)
    bymodel=query('SELECT modelo_id,sum(unidades)::float unidades,sum(receita_usd)/nullif(sum(unidades_com_preco),0) preco FROM mv_agregados a WHERE '+clause+' GROUP BY modelo_id',p)
    vals=np.array([r['unidades'] for r in bymodel],float)
    pairs=np.array([[r['preco'],r['unidades']] for r in bymodel if r['preco'] is not None],float)
    corr=float(np.corrcoef(pairs.T)[0,1]) if len(pairs)>=3 and np.std(pairs[:,0])>0 and np.std(pairs[:,1])>0 else None
    desc=dict(modelos=len(vals),media=float(np.mean(vals)) if len(vals) else None,mediana=float(np.median(vals)) if len(vals) else None,desvio_padrao=float(np.std(vals,ddof=1)) if len(vals)>1 else None,minimo=float(np.min(vals)) if len(vals) else None,maximo=float(np.max(vals)) if len(vals) else None,hhi=float(np.sum((vals/vals.sum()*100)**2)) if len(vals) and vals.sum()>0 else None)
    # Preços observacionais são consultados na fato, com o mesmo recorte; anual sintético é agregado de meses.
    pf=f
    pc,pp=where(pf)
    if f.periodicidade=='anual' and pf.periodicidade=='mensal':pc=pc.replace(' AND a.mes=%s','');pp.pop(5)
    prices=query('''SELECT count(preco_usd)::bigint n,percentile_cont(ARRAY[.05,.25,.5,.75,.95]) WITHIN GROUP(ORDER BY preco_usd) quantis,
        min(data_cambio) data_base FROM fato_vendas a WHERE '''+pc+' AND preco_usd IS NOT NULL',pp,True)
    return dict(segmentos=rows,descritiva=desc,correlacao_preco_unidades=corr,pares_correlacao=len(pairs),boxplot=prices,nota='Correlação descreve associação na cobertura observada, sem inferência causal. HHI refere-se ao recorte carregado, não necessariamente ao mercado completo.')
