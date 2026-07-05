"""Pydantic models for the PPF Annuaire (directory) write-path request bodies.

Field names, types, and required/optional status are taken from the bundled
swagger `specs/dgfip/swagger/ppf-openapi-annuaire-api-public-1.11.0-openapi.json`
(`components.schemas`). Attribute names are snake_case; aliases carry the
exact wire field names so `model_dump(by_alias=True, exclude_none=True)`
produces a body matching the swagger contract.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

_ALIASED = ConfigDict(populate_by_name=True)


class AdresseWrite(BaseModel):
    """`adresseWrite` — postal address for a code-routage."""

    model_config = _ALIASED

    ligne_adresse_1: Optional[str] = Field(default=None, alias="ligneAdresse1")
    ligne_adresse_2: Optional[str] = Field(default=None, alias="ligneAdresse2")
    ligne_adresse_3: Optional[str] = Field(default=None, alias="ligneAdresse3")
    code_postal: Optional[str] = Field(default=None, alias="codePostal")
    sub_division_pays: Optional[str] = Field(default=None, alias="subDivisionPays")
    localite: Optional[str] = None
    code_pays: Optional[str] = Field(default=None, alias="codePays")


class CreateCodeRoutageBody(BaseModel):
    """`createCodeRoutageBody` — POST /code-routage."""

    model_config = _ALIASED

    nature_etablissement: Literal["Privé", "Public"] = Field(alias="natureEtablissement")
    identifiant_routage: str = Field(alias="identifiantRoutage", max_length=100)
    siret: str = Field(pattern=r"^\d{14}$")
    type_identifiant_routage: str = Field(alias="typeIdentifiantRoutage", pattern=r"^\d{4}$")
    libelle_code_routage: str = Field(alias="libelleCodeRoutage", max_length=100)
    gestion_engagement_juridique: Optional[bool] = Field(
        default=None, alias="gestionEngagementJuridique"
    )
    etat_administratif: Literal["A", "F"] = Field(alias="etatAdministratif")
    adresse: Optional[AdresseWrite] = None


class UpdatePutCodeRoutageBody(BaseModel):
    """`updatePutCodeRoutageBody` — PUT /code-routage/id-instance:{id-instance}."""

    model_config = _ALIASED

    type_identifiant_routage: str = Field(alias="typeIdentifiantRoutage")
    libelle_code_routage: str = Field(alias="libelleCodeRoutage")
    etat_administratif: Literal["A", "F"] = Field(alias="etatAdministratif")
    adresse: Optional[AdresseWrite] = None


class UpdatePatchCodeRoutageBody(BaseModel):
    """`updatePatchCodeRoutageBody` — PATCH /code-routage/id-instance:{id-instance}."""

    model_config = _ALIASED

    type_identifiant_routage: Optional[str] = Field(default=None, alias="typeIdentifiantRoutage")
    libelle_code_routage: Optional[str] = Field(default=None, alias="libelleCodeRoutage")
    etat_administratif: Optional[Literal["A", "F"]] = Field(
        default=None, alias="etatAdministratif"
    )
    adresse: Optional[AdresseWrite] = None


class PeriodeEffet(BaseModel):
    """`createLigneAnnuaireBody_periodeEffet`."""

    model_config = _ALIASED

    date_debut_effet: str = Field(alias="dateDebutEffet")
    date_fin_effet: Optional[str] = Field(default=None, alias="dateFinEffet")


class InformationAdressage(BaseModel):
    """`createLigneAnnuaireBody_informationAdressage`."""

    model_config = _ALIASED

    siren: str
    siret: Optional[str] = None
    identifiant_routage: Optional[str] = Field(default=None, alias="identifiantRoutage")
    suffixe_adressage: Optional[str] = Field(default=None, alias="suffixeAdressage")
    matricule_plateforme: str = Field(alias="matriculePlateforme", pattern=r"^\d{4}$")


class CreateLigneAnnuaireBody(BaseModel):
    """`createLigneAnnuaireBody` — POST /ligne-annuaire."""

    model_config = _ALIASED

    periode_effet: Optional[PeriodeEffet] = Field(default=None, alias="periodeEffet")
    information_adressage: Optional[InformationAdressage] = Field(
        default=None, alias="informationAdressage"
    )


class UpdatePutLigneAnnuaireBody(BaseModel):
    """`updatePutLigneAnnuaireBody` — PUT /ligne-annuaire/id-instance:{id-instance}."""

    model_config = _ALIASED

    date_fin_effet: Optional[str] = Field(default=None, alias="dateFinEffet")
    matricule_plateforme: str = Field(alias="matriculePlateforme", pattern=r"^\d{4}$")


class UpdatePatchLigneAnnuaireBody(BaseModel):
    """`updatePatchLigneAnnuaireBody` — PATCH /ligne-annuaire/id-instance:{id-instance}."""

    model_config = _ALIASED

    date_fin_effet: Optional[str] = Field(default=None, alias="dateFinEffet")
    matricule_plateforme: Optional[str] = Field(
        default=None, alias="matriculePlateforme", pattern=r"^\d{4}$"
    )
