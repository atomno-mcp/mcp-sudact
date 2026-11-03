"""Client validation of confirmed REST fields; no search implementation."""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Court = Literal["any", "vs", "arbitr", "soyu", "ks", "fas"]
Instance = Literal["any"]
Anonymization = Literal["none", "physical_persons", "all_persons"]


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=3)
    court_type: Court = "any"
    instance: Instance = "any"
    norms: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    limit: int = Field(default=10, ge=1, le=50, strict=True)
    page: int | None = Field(default=None, ge=1, le=5, strict=True)
    fas_body: str | None = None
    fas_law: str | None = None
    fas_act_type: str | None = None

    @model_validator(mode="after")
    def confirmed_constraints(self):
        for name in ("date_from", "date_to"):
            value = getattr(self, name)
            if value is not None:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("ISO date required")
                date.fromisoformat(value)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date order")
        for name in ("fas_body", "fas_law", "fas_act_type"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, value.strip() or None)
        if self.fas_law:
            law = (
                self.fas_law.upper()
                .replace("FZ", "ФЗ")
                .replace(" ", "")
                .replace("–", "-")
                .replace("—", "-")
            )
            match = re.fullmatch(r"(44|223|135|38)-?ФЗ", law)
            if not match:
                raise ValueError("FAS law")
            self.fas_law = match[1] + "-ФЗ"
        if self.fas_act_type:
            act = self.fas_act_type.lower().replace("ё", "е")
            act = {
                "штраф": "постановление о штрафе",
                "постановление о наложении штрафа": "постановление о штрафе",
            }.get(act, act)
            if act not in (
                "решение",
                "предписание",
                "постановление",
                "постановление о штрафе",
                "определение",
                "предупреждение",
                "жалоба",
                "уведомление",
            ):
                raise ValueError("FAS act type")
            self.fas_act_type = act
        has_fas = any((self.fas_body, self.fas_law, self.fas_act_type))
        if has_fas and self.court_type not in ("any", "fas"):
            raise ValueError("FAS filter requires any/fas")
        if self.page is not None and (
            self.court_type not in ("vs", "arbitr", "soyu", "ks")
            or has_fas
            or self.page * self.limit > 50
        ):
            raise ValueError("page requires one section/no FAS filters/page*limit<=50")
        return self


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str | None = None
    case_id: str | None = None
    include_full_text: bool = True
    anonymize_level: Anonymization = "none"

    @model_validator(mode="after")
    def identifier(self):
        if not (self.url and self.url.strip()) and not (self.case_id and self.case_id.strip()):
            raise ValueError("url or case_id required")
        return self
