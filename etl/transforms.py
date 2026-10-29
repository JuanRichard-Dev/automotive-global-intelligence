"""Transformações distribuídas, sem UDF Python e sem imputar métricas reais."""
from pyspark.sql import functions as F,types as T

RAW_SCHEMA=T.StructType([T.StructField(name,typ,True) for name,typ in [
 ('record_id',T.LongType()),('country_iso',T.StringType()),('state_code',T.StringType()),('city',T.StringType()),
 ('year',T.IntegerType()),('month',T.IntegerType()),('period_kind',T.StringType()),('brand',T.StringType()),('model',T.StringType()),
 ('segment',T.StringType()),('fuel',T.StringType()),('price',T.DoubleType()),('currency',T.StringType()),('units',T.LongType()),
 ('metric',T.StringType()),('source_id',T.StringType()),('origin',T.StringType()),('reference_period',T.StringType()),
 ('record_origin',T.StringType()),('hash_origin',T.StringType()),('collected_at',T.DateType())]])

def normalize(df):
    def norm(c):return F.upper(F.regexp_replace(F.trim(F.col(c)),r'\s+',' '))
    df=df.withColumn('country_iso',norm('country_iso')).withColumn('brand',norm('brand')).withColumn('model',norm('model'))
    df=df.withColumn('brand',F.when(F.col('brand').isin('VW','VOLKSWAGEN'),'VOLKSWAGEN').when(F.col('brand').isin('GM','CHEVROLET'),'CHEVROLET').when(F.col('brand').isin('MERCEDES','MERCEDES BENZ','M.BENZ'),'MERCEDES-BENZ').otherwise(F.col('brand')))
    for c in ['state_code','currency','city']:df=df.withColumn(c,norm(c))
    for c in ['segment','fuel']:
        df=df.withColumn(c,F.when(F.col(c).isNull()|(F.trim(F.col(c))==''),'nao_informado').otherwise(F.lower(F.trim(F.col(c)))))
    df=df.withColumn('fuel',F.when(F.col('fuel')=='outros','outro').otherwise(F.col('fuel')))
    df=df.withColumn('period_kind',F.create_map(F.lit('annual'),F.lit('anual'),F.lit('monthly'),F.lit('mensal'),F.lit('quarterly'),F.lit('trimestral'))[F.col('period_kind')])
    return df.withColumn('model_key',F.sha2(F.concat_ws('|','brand','model'),256))

def validate(df,country_codes,state_pairs,source_ids):
    # Sem denominador ou informação na fonte, não há preenchimento artificial.
    reasons=F.concat_ws(';',
      F.when(F.col('record_id').isNull(),'identificador_ausente'),
      F.when(~F.col('country_iso').isin(country_codes)|F.col('country_iso').isNull(),'pais_invalido'),
      F.when(F.col('year').isNull()|~F.col('year').between(2021,2027),'ano_invalido'),
      F.when(F.col('units').isNull()|(F.col('units')<0),'unidades_invalidas'),
      F.when(F.col('brand').isNull()|(F.length('brand')==0)|F.col('model').isNull()|(F.length('model')==0),'modelo_ausente'),
      F.when(~F.col('source_id').isin(source_ids)|F.col('source_id').isNull(),'fonte_invalida'),
      F.when((F.col('origin')!='real')|F.col('origin').isNull(),'origem_invalida'),
      F.when(F.col('source_id').startswith('SYN'),'fonte_nao_publicada'),
      F.when(F.col('period_kind').isNull(),'periodo_invalido'),
      F.when((F.col('period_kind')!='anual')&(F.col('month').isNull()|~F.col('month').between(1,12)),'mes_invalido'),
      F.when((F.col('period_kind')=='trimestral')&~F.col('month').isin(3,6,9,12),'trimestre_invalido'),
      F.when(F.col('price')<0,'preco_negativo'),
      F.when(F.isnan('price')|(F.abs(F.col('price'))==float('inf')),'preco_nao_finito'),
      F.when(F.col('collected_at').isNull(),'data_invalida'),
      F.when(F.col('metric').isNull()|~F.col('metric').isin('new_registrations','new_vehicle_sales','first_registrations_including_imports'),'medida_invalida'))
    # Estados precisam pertencer ao país; códigos apenas com sigla são normalizados explicitamente.
    allowed=[a+'|'+b for a,b in state_pairs]
    reasons=F.concat_ws(';',reasons,F.when(F.col('state_code').isNotNull()&~F.concat_ws('|','country_iso','state_code').isin(allowed),'estado_pais_incompativel'))
    flagged=df.withColumn('motivo_rejeicao',reasons)
    rejected=flagged.filter(F.length('motivo_rejeicao')>0)
    valid=flagged.filter(F.length('motivo_rejeicao')==0).drop('motivo_rejeicao')
    extreme=valid.filter((F.col('price')>10000000)|(F.col('units')>1000000000))
    clean=valid.filter(~((F.coalesce(F.col('price'),F.lit(0))>10000000)|(F.col('units')>1000000000)))
    return clean,rejected,extreme
