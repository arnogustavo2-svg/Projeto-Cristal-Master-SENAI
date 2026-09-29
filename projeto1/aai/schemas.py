from datetime import date
from typing import Literal, Optional, Union, List
from pydantic import BaseModel, Field, FiniteFloat


class MaterialCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    descricao: str = Field(min_length=1, max_length=200)
    unidade: str = Field(min_length=1, max_length=20)


class MaterialUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1, max_length=200)
    unidade: Optional[str] = Field(default=None, min_length=1, max_length=20)
    ativo: Optional[bool] = None


class OperadorCreate(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=1, max_length=120)
    funcao: Literal["separador", "empilhadeira"] = "separador"


class OperadorUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=120)
    ativo: Optional[bool] = None
    funcao: Optional[Literal["separador", "empilhadeira"]] = None


class OperatorLookup(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)


class PosicaoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    descricao: Optional[str] = Field(default=None, max_length=200)


class LoteCreate(BaseModel):
    material_id: int
    codigo: str = Field(min_length=1, max_length=50)
    validade: Optional[date] = None


class PalletCreate(BaseModel):
    lote_id: int
    codigo: str = Field(min_length=1, max_length=50)
    posicao_id: Optional[int] = None


class PalletBloqueio(BaseModel):
    bloqueado: bool


class ItemOPCreate(BaseModel):
    material_id: int
    quantidade: float = Field(gt=0)


class OrdemProducaoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    produto: str = Field(min_length=1, max_length=200)
    prioridade: int = Field(default=3, ge=1, le=5)
    prazo: Optional[date] = None
    itens: List[ItemOPCreate] = []


class GerarTarefasInput(BaseModel):
    operador_id: Optional[int] = None


class TarefaInicio(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)


class TarefaConclusao(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)
    quantidade_retirada: float = Field(gt=0)
    pallet_id: Optional[int] = None
    posicao_id: Optional[int] = None
    observacao: Optional[str] = Field(default=None, max_length=500)


class EntradaEstoque(BaseModel):
    material_id: int
    lote_id: Optional[int] = None
    pallet_id: Optional[int] = None
    posicao_id: Optional[int] = None
    quantidade: float = Field(gt=0)
    observacao: Optional[str] = Field(default=None, max_length=500)


class DemandaItemCreate(BaseModel):
    codigo_material: str = Field(min_length=1, max_length=50)
    descricao_material: str = Field(min_length=1, max_length=200)
    localizacao: str = Field(min_length=1, max_length=100)
    quantidade_por_carga: FiniteFloat = Field(gt=0)
    unidade: str = Field(min_length=1, max_length=20)
    fornecedor: str = Field(min_length=1, max_length=120)
    peso_sacaria: FiniteFloat = Field(gt=0)
    capacidade_pallet: FiniteFloat = Field(gt=0)
    observacao: Optional[str] = Field(default=None, max_length=500)


class DemandaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    produto: str = Field(min_length=1, max_length=200)
    quantidade_cargas: int = Field(gt=0, le=100000)
    itens: List[DemandaItemCreate] = Field(min_length=1, max_length=100)
    observacao: Optional[str] = Field(default=None, max_length=1000)


class FechamentoPallet(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)
    sacarias: int = Field(ge=0)
    quantidade_pesagem: FiniteFloat = Field(ge=0)
    posicao_id: Optional[int] = None


class MovimentarPallet(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)
    posicao_destino_id: int


class AjusteEstoqueCreate(BaseModel):
    material_id: int
    lote_id: Optional[int] = None
    pallet_id: Optional[int] = None
    posicao_anterior_id: Optional[int] = None
    posicao_id: Optional[int] = None
    quantidade_ajuste: FiniteFloat
    tipo: Literal[
        "falta_fisica", "sobra_fisica", "pallet_encontrado",
        "lote_incorreto", "posicao_incorreta", "pallet_sem_identificacao",
    ]
    motivo: str = Field(min_length=1, max_length=200)
    observacao: Optional[str] = Field(default=None, max_length=500)
    responsavel: str = Field(min_length=1, max_length=120)


class DemandaInterpretadaItem(BaseModel):
    codigo_material: Optional[str] = Field(default=None, max_length=50)
    descricao_material: Optional[str] = Field(default=None, max_length=200)
    localizacao: Optional[str] = Field(default=None, max_length=100)
    quantidade_por_carga: Optional[FiniteFloat] = None
    unidade: Optional[str] = Field(default=None, max_length=20)
    fornecedor: Optional[str] = Field(default=None, max_length=120)
    peso_sacaria: Optional[FiniteFloat] = None
    capacidade_pallet: Optional[FiniteFloat] = None
    observacao: Optional[str] = Field(default=None, max_length=500)


class DemandaInterpretada(BaseModel):
    codigo: Optional[str] = Field(default=None, max_length=50)
    produto: Optional[str] = Field(default=None, max_length=200)
    quantidade_cargas: Optional[int] = Field(default=None, gt=0)
    itens: List[DemandaInterpretadaItem] = Field(default_factory=list, max_length=100)
    observacao: Optional[str] = Field(default=None, max_length=1000)


class GeminiFileInput(BaseModel):
    nome_arquivo: str = Field(min_length=1, max_length=255)
    mime_type: Literal["image/jpeg", "image/png", "image/webp", "application/pdf"]
    conteudo_base64: str = Field(min_length=1, max_length=28000000)


class ExcecaoCreate(BaseModel):
    tarefa_id: Optional[int] = None
    matricula: Optional[str] = Field(default=None, max_length=50)
    operador_id: Optional[int] = None
    motivo: str = Field(min_length=1, max_length=100)
    observacao: Optional[str] = Field(default=None, max_length=500)


class ExcecaoResolucao(BaseModel):
    decisao: str = Field(min_length=1, max_length=500)


class DeviceEventCreate(BaseModel):
    evento_id: str = Field(min_length=1, max_length=100)
    dispositivo_id: str = Field(min_length=1, max_length=100)
    baia: Optional[str] = Field(default=None, max_length=50)
    uid_rfid: Optional[str] = Field(default=None, max_length=100)
    tipo_evento: str = Field(min_length=1, max_length=100)
    valor: Optional[Union[str, bool, int, float]] = None
