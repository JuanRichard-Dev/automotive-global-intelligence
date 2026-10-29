import argparse,csv,hashlib,json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,unquote
from pyspark.sql import SparkSession,functions as F,Window,types as T
from .common import ROOT,DATA,DSN,connect,init_schema,upsert,load_json
from .bootstrap import metadata,media
from .transforms import RAW_SCHEMA,normalize,validate

def session():
    jar=ROOT/'etl/jars/postgresql-42.7.14.jar'
    builder=(SparkSession.builder.appName('MotorAtlasETL').master(os.getenv('SPARK_MASTER','local[2]'))
      .config('spark.driver.memory',os.getenv('SPARK_DRIVER_MEMORY','2g'))
      .config('spark.sql.shuffle.partitions','8').config('spark.sql.adaptive.enabled','true')
      .config('spark.ui.enabled','false')
      .config('spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version','2')
      .config('spark.driver.host','127.0.0.1'))
    if os.name=='nt':
        import subprocess,pyspark
        target=ROOT/'etl/windows/classes';target.mkdir(exist_ok=True)
        java=Path(os.environ['JAVA_HOME'])/'bin'
        jars=Path(pyspark.__file__).parent/'jars'
        cp=os.pathsep.join(str(p) for p in jars.glob('hadoop-client-api-*.jar'))
        subprocess.run([str(java/'javac.exe'),'-proc:none','-cp',cp,'-d',str(target),str(ROOT/'etl/windows/PortableLocalFileSystem.java')],check=True)
        builder=builder.config('spark.driver.extraClassPath',os.pathsep.join([str(jar),str(target)])).config('spark.hadoop.fs.file.impl','atlas.PortableLocalFileSystem')
    else:builder=builder.config('spark.jars',str(jar))
    return builder.getOrCreate()

def input_manifest():
    """Hash dos arquivos de evidência e das regras que determinam a carga."""
    paths=[DATA/'raw/real_sales.csv',DATA/'raw/market_totals.csv']
    paths += [DATA/'seed'/name for name in ('sources.json','media.json','fx.json','world.geojson','states-br-us.geojson')]
    paths += [ROOT/name for name in ('etl/pipeline.py','etl/transforms.py','etl/aggregations.py','etl/bootstrap.py','db/001_schema.sql','db/002_seed.sql','db/003_views.sql')]
    files={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    fingerprint=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    with (DATA/'raw/real_sales.csv').open(encoding='utf8',newline='') as stream:
        real_rows=sum(1 for _ in csv.DictReader(stream))
    if not real_rows:raise ValueError('A entrada real está vazia; nenhuma carga foi iniciada')
    return fingerprint,files,real_rows

def run(rows=0,seed=0,force=False):
    # Parâmetros legados permanecem aceitos apenas no modo sem geração.
    if rows!=0:raise ValueError('A carga aceita apenas dados reais: --rows deve ser 0')
    fingerprint,files,real_rows=input_manifest()
    started=datetime.now(timezone.utc);run_id=str(uuid.uuid4())
    with connect() as conn:
        init_schema(conn)
        existing=conn.execute("SELECT status,qualidade FROM execucao_etl ORDER BY iniciada_em DESC LIMIT 1").fetchone()
        current=conn.execute("SELECT count(*) FILTER(WHERE origem='real') reais,count(*) FILTER(WHERE origem<>'real') outras FROM fato_vendas").fetchone()
        quality=(existing or {}).get('qualidade') or {}
        if existing and existing['status']=='concluida' and quality.get('modo')=='real' and quality.get('fingerprint_entrada')==fingerprint and quality.get('recebidos')==real_rows and quality.get('tratados')==current['reais'] and current['outras']==0 and not force:
            print('Carga real já concluída para os mesmos arquivos e regras. Use --force para reconstruir.');return
        conn.execute('INSERT INTO execucao_etl(id,iniciada_em,seed,linhas_sinteticas,status) VALUES (%s,%s,0,0,%s)',(run_id,started,'iniciada'))
        metadata(conn)
    spark=session();spark.sparkContext.setLogLevel('WARN')
    report=dict(execucao=run_id,modo='real',fingerprint_entrada=fingerprint,arquivos_sha256=files,linhas_entrada_real=real_rows,iniciada_em=started.isoformat())
    try:
        raw_real=spark.read.option('header',True).schema(RAW_SCHEMA).csv(str(DATA/'raw/real_sales.csv'))
        bronze=DATA/'bronze'/'real'
        print('Gravando evidência real bronze Parquet particionada por país/ano…',flush=True)
        raw_real.write.mode('overwrite').partitionBy('country_iso','year').parquet(str(bronze))
        raw=spark.read.schema(RAW_SCHEMA).parquet(str(bronze))
        normal=normalize(raw).persist()
        with connect() as conn:
            countries=list(conn.execute('SELECT id,iso FROM dim_pais'));states=list(conn.execute('SELECT id,pais_id,codigo FROM dim_estado'));sourceids=[r['id'] for r in conn.execute('SELECT id FROM fonte_dados')]
            country_by_id={r['id']:r['iso'] for r in countries}
            state_pairs=[(country_by_id[r['pais_id']],r['codigo']) for r in states]
        clean,rejected,extreme=validate(normal,[r['iso'] for r in countries],state_pairs,sourceids)
        clean=clean.dropDuplicates(['origin','source_id','record_id']).persist()
        report['recebidos']=normal.count();report['rejeitados']=rejected.count();report['revisao_outliers']=extreme.count();report['tratados']=clean.count()
        report['duplicidades']=report['recebidos']-report['rejeitados']-report['revisao_outliers']-report['tratados']
        report['origens']={r['origin']:r['count'] for r in clean.groupBy('origin').count().collect()}
        report['campos_ausentes']={c:clean.filter(F.col(c).isNull()).count() for c in ['state_code','city','price','currency']}
        for name,frame in [('rejeitados',rejected),('revisao_outliers',extreme)]:
            if report[name] if name in report else False:
                frame.write.mode('overwrite').parquet(str(DATA/'quarantine'/run_id/name))
        brands=clean.select('brand').distinct().withColumn('id',F.row_number().over(Window.orderBy('brand')))
        models=clean.select('brand','model','model_key').distinct().join(brands.withColumnRenamed('id','marca_id'),'brand').withColumn('id',F.row_number().over(Window.orderBy('brand','model')))
        with connect() as conn:
            # A carga pertence a este banco dedicado; o original e os intermediários são preservados.
            conn.execute('TRUNCATE fato_vendas,fato_mercado')
            conn.execute('DELETE FROM midia');conn.execute('DELETE FROM dim_modelo');conn.execute('DELETE FROM dim_marca')
            conn.execute("DELETE FROM dim_cidade WHERE tipo='sintetica' OR codigo LIKE '%SYN%'")
            conn.execute("DELETE FROM fonte_dados WHERE id LIKE 'SYN%' OR tipo='sintetica'")
            # Migração de bancos anteriores só ocorre depois de remover os fatos antigos.
            for table in ('fato_vendas','fato_mercado'):
                conn.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_somente_real')
                conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_somente_real CHECK (origem='real' AND fonte_id NOT LIKE 'SYN%')")
            upsert(conn,'dim_marca',[dict(id=r.id,nome=r.brand) for r in brands.collect()])
            upsert(conn,'dim_modelo',[dict(id=r.id,marca_id=r.marca_id,nome=r.model,chave=r.model_key) for r in models.collect()])
            for r in clean.select('year').distinct().collect():conn.execute('SELECT garantir_particao_vendas(%s)',(r.year,))
            conn.commit()
        def csv_dim(name,schema):return spark.read.option('header',True).schema(schema).csv(str(DATA/'seed'/name))
        pc=csv_dim('countries.csv','pais_id int, country_iso string, pais_nome string')
        es=csv_dim('states.csv','estado_id int, estado_pais_id int, state_code string')
        ci=csv_dim('cities.csv','cidade_id int, city string, cidade_pais_id int, cidade_estado_id int')
        seg=spark.createDataFrame([(0,'nao_informado'),(1,'suv'),(2,'sedan'),(3,'hatch'),(4,'picape')],['segmento_id','segment'])
        fuel=spark.createDataFrame([(0,'nao_informado'),(1,'gasolina'),(2,'flex'),(3,'diesel'),(4,'hibrido'),(5,'eletrico'),(6,'outro'),(7,'gas'),(8,'hidrogenio')],['combustivel_id','fuel'])
        fx=spark.read.option('multiLine',True).json(str(DATA/'seed/fx.json')).select(F.col('moeda').alias('currency'),F.col('usd_por_unidade').alias('rate'),F.to_date('data_referencia').alias('fx_date'))
        enriched=(clean.join(F.broadcast(pc),'country_iso').join(F.broadcast(es),'state_code','left').join(F.broadcast(ci),'city','left')
          .join(F.broadcast(models.select('model_key',F.col('id').alias('modelo_id'),'marca_id')),'model_key')
          .join(F.broadcast(seg),'segment','left').join(F.broadcast(fuel),'fuel','left').join(F.broadcast(fx),'currency','left'))
        report['precos_sem_cambio']=enriched.filter(F.col('price').isNotNull()&F.col('rate').isNull()).count()
        # Ausência de segmento/combustível não exclui registros reais de vendas.
        facts=enriched.select(
          F.col('year').cast('short').alias('ano'),F.col('record_id').alias('registro_id'),F.col('pais_id').cast('short'),F.col('estado_id').cast('int'),F.col('cidade_id').cast('int'),
          F.col('marca_id').cast('int'),F.col('modelo_id').cast('int'),F.coalesce('segmento_id',F.lit(0)).cast('short').alias('segmento_id'),F.coalesce('combustivel_id',F.lit(6)).cast('short').alias('combustivel_id'),
          (F.col('year')*10000+F.coalesce('month',F.lit(1))*100+1).cast('int').alias('tempo_id'),F.col('source_id').alias('fonte_id'),F.col('origin').alias('origem'),F.col('metric').alias('medida'),F.col('period_kind').alias('periodicidade'),
          F.when(F.col('period_kind')!='anual',F.col('month')).cast('short').alias('mes'),F.col('units').alias('unidades'),F.col('price').cast('decimal(16,2)').alias('preco_original'),F.col('currency').alias('moeda_original'),
          F.when(F.col('price').isNotNull(),F.col('rate')).cast('decimal(20,10)').alias('cambio_usd'),F.round(F.col('price')*F.col('rate'),2).cast('decimal(16,2)').alias('preco_usd'),
          F.when(F.col('price').isNotNull(),F.col('fx_date')).alias('data_cambio'),F.col('record_origin').alias('registro_origem'),F.col('hash_origin').alias('hash_origem'),F.col('collected_at').alias('coletado_em'))
        silver=DATA/'silver'
        print('Gravando silver Parquet particionado por país/ano…',flush=True)
        facts.join(F.broadcast(pc.select('pais_id','country_iso')),'pais_id').write.mode('overwrite').partitionBy('country_iso','ano').parquet(str(silver))
        facts=spark.read.parquet(str(silver)).drop('country_iso')
        # Window functions: origem/medida e periodicidades nunca são misturadas.
        from .aggregations import annual_ranking,monthly_seasonality
        annual_ranking(clean).filter(F.col('posicao')<=10).write.mode('overwrite').parquet(str(DATA/'analytics/rankings_spark'))
        annual_ranking(clean,state=True).filter(F.col('posicao')<=10).write.mode('overwrite').parquet(str(DATA/'analytics/rankings_estado_spark'))
        monthly_seasonality(clean).write.mode('overwrite').parquet(str(DATA/'analytics/sazonalidade_pais_spark'))
        monthly_seasonality(clean,state=True).write.mode('overwrite').parquet(str(DATA/'analytics/sazonalidade_estado_spark'))
        jdbc=urlparse(DSN);url=f'jdbc:postgresql://{jdbc.hostname}:{jdbc.port or 5432}/{jdbc.path.lstrip("/")}?reWriteBatchedInserts=true'
        print(f'Carga JDBC de {report["tratados"]:,} observações…',flush=True)
        facts.coalesce(4).write.format('jdbc').option('url',url).option('dbtable','fato_vendas').option('user',unquote(jdbc.username or '')).option('password',unquote(jdbc.password or '')).option('driver','org.postgresql.Driver').option('batchsize','10000').mode('append').save()
        import csv
        with connect() as conn:
            countrymap={r['iso']:r['id'] for r in conn.execute('SELECT id,iso FROM dim_pais')};fuelmap={r['codigo']:r['id'] for r in conn.execute('SELECT id,codigo FROM dim_combustivel')}
            fuelmap['outros']=fuelmap['outro']
            with (DATA/'raw/market_totals.csv').open(encoding='utf8') as f:
                records=list(csv.DictReader(f))
            with conn.cursor() as cur:
                cur.executemany('INSERT INTO fato_mercado(pais_id,ano,mes,periodicidade,origem,medida,combustivel_id,unidades,fonte_id,observacao) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',[(countrymap[r['country_iso']],int(r['year']),int(r['month']) if r.get('month') else None,{'annual':'anual','monthly':'mensal','quarterly':'trimestral'}[r['period_kind']],'real',r['metric'],fuelmap.get(r.get('fuel')) if r.get('fuel') else None,int(r['units']),r['source_id'],r['scope']) for r in records])
            media(conn)
            print('Atualizando materialized views e estatísticas…',flush=True)
            conn.execute((ROOT/'db/003_views.sql').read_text(encoding='utf8'))
            conn.execute('ANALYZE fato_vendas')
            count=conn.execute('SELECT count(*) n FROM fato_vendas').fetchone()['n']
            if count!=report['tratados']:raise ValueError('Carga JDBC divergiu da contagem tratada')
            report['carregados_postgresql']=count;report['terminada_em']=datetime.now(timezone.utc).isoformat()
            conn.execute("UPDATE execucao_etl SET status='concluida',terminada_em=now(),qualidade=%s WHERE id=%s",(psycopg_json(report),run_id));conn.commit()
        (ROOT/'docs').mkdir(exist_ok=True)
        (ROOT/'docs/qualidade_etl.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        return report
    except Exception as e:
        with connect() as conn:conn.execute("UPDATE execucao_etl SET status='falhou',terminada_em=now(),qualidade=%s WHERE id=%s",(psycopg_json(dict(erro=str(e))),run_id))
        raise
    finally:spark.stop()

def psycopg_json(value):
    from psycopg.types.json import Jsonb
    return Jsonb(value)

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Carga de evidência real publicada');p.add_argument('--rows',type=int,default=0,help=argparse.SUPPRESS);p.add_argument('--seed',type=int,default=0,help=argparse.SUPPRESS);p.add_argument('--force',action='store_true');a=p.parse_args();run(a.rows,a.seed,a.force)
