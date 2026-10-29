from typing import Literal
from pydantic import BaseModel,Field,model_validator

class Filters(BaseModel):
    pais:str=Field(default='BR',pattern=r'^[A-Z]{2}$')
    estado:str|None=Field(default=None,pattern=r'^[A-Z]{2}-[A-Z0-9]{1,3}$')
    cidade:str|None=Field(default=None,max_length=120,pattern=r'^[A-Z0-9À-Ú .\-]+$')
    ano:int=Field(default=2025,ge=2021,le=2027)
    origem:Literal['real']='real'
    medida:Literal['new_registrations','new_vehicle_sales','first_registrations_including_imports']|None=None
    periodicidade:Literal['anual','mensal','trimestral']='anual'
    mes:int|None=Field(default=None,ge=1,le=12)
    segmento:str|None=Field(default=None,max_length=32,pattern=r'^[a-z_]+$')
    combustivel:str|None=Field(default=None,max_length=32,pattern=r'^[a-z_]+$')
    @model_validator(mode='after')
    def period(self):
        if self.periodicidade!='anual' and self.mes is None:raise ValueError('Mês final obrigatório para mês/trimestre')
        if self.periodicidade=='trimestral' and self.mes not in (3,6,9,12):raise ValueError('Trimestre deve terminar em 3,6,9 ou 12')
        if self.periodicidade=='anual' and self.mes is not None:raise ValueError('Ano completo não aceita filtro de mês')
        if self.estado and not self.estado.startswith(self.pais+'-'):raise ValueError('Estado deve pertencer ao país')
        if self.cidade and not self.estado:raise ValueError('Cidade exige um estado selecionado')
        return self

class Page(BaseModel):
    pagina:int=Field(default=1,ge=1,le=10000)
    tamanho:int=Field(default=10,ge=1,le=100)
