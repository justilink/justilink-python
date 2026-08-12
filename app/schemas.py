from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models import (
    RoleUtilisateur, StatutDossier, StatutAdmissibilite,
    StatutDocument, StatutTransmission, TypeMatiereJudiciaire
)


class LoginSchema(BaseModel):
    email: EmailStr
    mot_de_passe: str


class UtilisateurPublic(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    role: RoleUtilisateur
    actif: bool
    mfa_active: bool
    cree_le: datetime
    model_config = {"from_attributes": True}


class UtilisateurDetail(UtilisateurPublic):
    derniere_connexion: Optional[datetime]
    modifie_le: datetime


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    utilisateur: UtilisateurPublic


class UtilisateurCreate(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    mot_de_passe: str = Field(..., min_length=8)
    role: RoleUtilisateur = RoleUtilisateur.CITOYEN

    @field_validator("mot_de_passe")
    @classmethod
    def mdp_complexite(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Au moins une majuscule requise")
        if not any(c.isdigit() for c in v):
            raise ValueError("Au moins un chiffre requis")
        return v


class DemandeAdmissibiliteCreate(BaseModel):
    date_naissance: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    adresse: str = Field(..., min_length=10)
    telephone: str
    nb_personnes_charge: int = Field(0, ge=0, le=20)
    revenu_annuel: float = Field(..., ge=0)
    actif_total: float = Field(0.0, ge=0)
    beneficiaire_aide_sociale: bool = False
    type_matiere: TypeMatiereJudiciaire
    description_litige: str = Field(..., min_length=20)


class DemandeAdmissibilitePublic(BaseModel):
    id: int
    numero_demande: str
    demandeur_id: int
    nb_personnes_charge: int
    revenu_annuel: float
    actif_total: float
    beneficiaire_aide_sociale: bool
    type_matiere: TypeMatiereJudiciaire
    description_litige: str
    statut: StatutAdmissibilite
    score_admissibilite: Optional[float]
    motif_decision: Optional[str]
    evalue_automatiquement: bool
    evalue_le: Optional[datetime]
    notes_agent: Optional[str]
    cree_le: datetime
    model_config = {"from_attributes": True}


class ResultatEvaluation(BaseModel):
    statut: StatutAdmissibilite
    score: float
    admissible: bool
    motif: str
    seuil_revenu_applicable: float
    details: dict


class DossierCreate(BaseModel):
    titre: str = Field(..., min_length=5, max_length=300)
    type_matiere: TypeMatiereJudiciaire
    description: Optional[str] = None
    nom_client: str = Field(..., min_length=2)
    nom_partie_adverse: Optional[str] = None
    priorite: int = Field(2, ge=1, le=3)
    tribunal: str = "Cour du Québec – District de Longueuil"
    date_audience: Optional[datetime] = None
    date_echeance: Optional[datetime] = None
    demande_admissibilite_id: Optional[int] = None
    tags: List[str] = []


class DossierUpdate(BaseModel):
    titre: Optional[str] = None
    statut: Optional[StatutDossier] = None
    priorite: Optional[int] = Field(None, ge=1, le=3)
    assignee_id: Optional[int] = None
    numero_greffe: Optional[str] = None
    date_audience: Optional[datetime] = None
    date_echeance: Optional[datetime] = None
    notes_internes: Optional[str] = None
    tags: Optional[List[str]] = None


class DossierPublic(BaseModel):
    id: int
    numero_dossier: str
    titre: str
    type_matiere: TypeMatiereJudiciaire
    statut: StatutDossier
    priorite: int
    nom_client: str
    nom_partie_adverse: Optional[str]
    assignee_id: Optional[int]
    tribunal: str
    numero_greffe: Optional[str]
    date_ouverture: datetime
    date_audience: Optional[datetime]
    date_echeance: Optional[datetime]
    date_cloture: Optional[datetime]
    tags: Any
    cree_le: datetime
    modifie_le: datetime
    model_config = {"from_attributes": True}


class DossierDetail(DossierPublic):
    description: Optional[str]
    notes_internes: Optional[str]
    demande_admissibilite_id: Optional[int]
    assignee: Optional[UtilisateurPublic]
    nb_documents: int = 0
    nb_transmissions: int = 0
    model_config = {"from_attributes": True}


class HistoriquePublic(BaseModel):
    id: int
    action: str
    details: Optional[str]
    auteur_id: Optional[int]
    cree_le: datetime
    model_config = {"from_attributes": True}


class DocumentPublic(BaseModel):
    id: int
    numero_document: str
    dossier_id: int
    deposeur_id: int
    nom_original: str
    type_fichier: str
    taille_octets: int
    categorie: str
    description: Optional[str]
    confidentiel: bool
    statut: StatutDocument
    signe_electroniquement: bool
    valide_le: Optional[datetime]
    cree_le: datetime
    model_config = {"from_attributes": True}


class TransmissionCreate(BaseModel):
    dossier_id: int
    documents_ids: List[int] = Field(..., min_length=1)
    objet_transmission: str = Field(..., min_length=5)
    message: Optional[str] = None
    greffe_destinataire: str = "Greffe – District de Longueuil"
    email_greffe: str = "greffe@tribunal-longueuil.gouv.qc.ca"


class TransmissionPublic(BaseModel):
    id: int
    numero_transmission: str
    dossier_id: int
    initiateur_id: int
    greffe_destinataire: str
    email_greffe: str
    objet_transmission: str
    documents_inclus: Any
    statut: StatutTransmission
    envoye_le: Optional[datetime]
    confirme_le: Optional[datetime]
    accuse_reception: Optional[str]
    tentatives: int
    protocole_chiffrement: str
    cree_le: datetime
    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_dossiers: int
    dossiers_ouverts: int
    dossiers_en_cours: int
    dossiers_cloturs: int
    demandes_admissibilite_total: int
    demandes_admissibles: int
    demandes_non_admissibles: int
    taux_automatisation_pct: float
    total_documents: int
    total_transmissions: int
    transmissions_reussies: int
    taux_succes_transmission_pct: float
    delai_moyen_traitement_h: float


class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[Any] = None
