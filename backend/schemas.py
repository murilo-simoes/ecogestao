"""Contratos de entrada e restrições independentes da interface."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Metric = Literal['agua', 'energia', 'residuos']


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid', allow_inf_nan=False)


class Login(Input):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=200)


class Sector(Input):
    name: str = Field(min_length=2, max_length=100)
    active: bool = True


class Partner(Sector):
    contact: str = Field(default='', max_length=200)


class Record(Input):
    metric: Metric
    date: date
    quantity: float = Field(gt=0, le=1_000_000_000)
    sector_id: int = Field(gt=0)
    partner_id: int | None = Field(default=None, gt=0)
    waste_type: str = Field(default='', max_length=100)
    destination: str = Field(default='', max_length=100)
    note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def coherent(self):
        if self.date > date.today():
            raise ValueError('A data do registro não pode estar no futuro.')
        if self.metric == 'residuos':
            if not all([self.partner_id, self.waste_type, self.destination]):
                raise ValueError('Resíduos exigem parceiro, tipo e destinação.')
        elif self.partner_id or self.waste_type or self.destination:
            raise ValueError('Dados de destinação são exclusivos de resíduos.')
        return self


class Goal(Input):
    title: str = Field(min_length=3, max_length=150)
    metric: Metric
    sector_id: int = Field(gt=0)
    start_date: date
    end_date: date
    limit_value: float = Field(gt=0, le=1_000_000_000)

    @model_validator(mode='after')
    def ordered(self):
        if self.end_date < self.start_date:
            raise ValueError('O fim do período deve ser igual ou posterior ao início.')
        return self


class Action(Input):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=5, max_length=2000)
    sector_id: int = Field(gt=0)
    owner_id: int = Field(gt=0)
    due_date: date
    status: Literal['aberta', 'em_andamento', 'concluida'] = 'aberta'
    evidence: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def completion(self):
        if self.status == 'concluida' and len(self.evidence) < 5:
            raise ValueError('Informe uma evidência de conclusão com pelo menos cinco caracteres.')
        if self.status != 'concluida' and self.evidence:
            raise ValueError('Evidência de conclusão somente para ação concluída.')
        return self
