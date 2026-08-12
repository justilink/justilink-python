from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Enum as SAEnum, Text, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


class RoleUtilisateur(str, enum.Enum):
    ADMIN    = "admin"
    GREFFIER = "greffier"
    AVOCAT   = "avocat"
    AGENT_AJ = "agent_aj"
    CITOYEN  = "citoyen"

class StatutDossier(str, enum.Enum):
    OUVERT     = "ouvert"
    EN_COURS   = "en_cours"
    EN_ATTENTE = "en_attente"
    CLOTURE    = "cloture"
    REJETE     = "rejete"

class StatutAdmissibilite(str, enum.Enum):
    EN_ATTENTE     = "en_attente"
    ADMISSIBLE     = "admissible"
    NON_ADMISSIBLE = "non_admissible"
    REVISION       = "revision_requise"

class StatutDocument(str, enum.Enum):
    DEPOSE        = "depose"
    EN_TRAITEMENT = "en_traitement"
    VALIDE        = "valide"
    REJETE        = "rejete"

class StatutTransmission(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    TRANSMIS   = "transmis"
    CONFIRME   = "confirme"
    ECHEC      = "echec"

class TypeMatiereJudiciaire(str, enum.Enum):
    CIVIL         = "civil"
    FAMILIAL      = "familial"
    LOGEMENT      = "logement"
    IMMIGRATION   = "immigration"
    PENAL_MINEUR  = "penal_mineur"
    ADMINISTRATIF = "administratif"


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id                 = Column(Integer, primary_key=True, index=True)
    nom                = Column(String(100), nullable=False)
    prenom             = Column(String(100), nullable=False)
    email              = Column(String(200), unique=True, index=True, nullable=False)
    mot_de_passe       = Column(String(255), nullable=False)
    role               = Column(SAEnum(RoleUtilisateur), nullable=False,
                                default=RoleUtilisateur.CITOYEN)
    actif              = Column(Boolean, default=True)
    mfa_active         = Column(Boolean, default=False)
    derniere_connexion = Column(DateTime, nullable=True)
    cree_le            = Column(DateTime, default=datetime.utcnow)
    modifie_le         = Column(DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)
    demandes_admissibilite = relationship("DemandeAdmissibilite",
                                          back_populates="demandeur")
    dossiers               = relationship("Dossier", back_populates="assignee")
    documents              = relationship("Document", back_populates="deposeur", foreign_keys="[Document.deposeur_id]")
    transmissions          = relationship("Transmission", back_populates="initiateur")

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"


class DemandeAdmissibilite(Base):
    __tablename__ = "demandes_admissibilite"
    id                        = Column(Integer, primary_key=True, index=True)
    numero_demande            = Column(String(20), unique=True, index=True)
    demandeur_id              = Column(Integer, ForeignKey("utilisateurs.id"),
                                       nullable=False)
    date_naissance            = Column(String(10))
    adresse                   = Column(Text)
    telephone                 = Column(String(20))
    nb_personnes_charge       = Column(Integer, default=0)
    revenu_annuel             = Column(Float, nullable=False)
    actif_total               = Column(Float, default=0.0)
    beneficiaire_aide_sociale = Column(Boolean, default=False)
    type_matiere              = Column(SAEnum(TypeMatiereJudiciaire), nullable=False)
    description_litige        = Column(Text)
    statut                    = Column(SAEnum(StatutAdmissibilite),
                                       default=StatutAdmissibilite.EN_ATTENTE)
    score_admissibilite       = Column(Float, nullable=True)
    motif_decision            = Column(Text, nullable=True)
    evalue_automatiquement    = Column(Boolean, default=False)
    evalue_le                 = Column(DateTime, nullable=True)
    cree_le                   = Column(DateTime, default=datetime.utcnow)
    modifie_le                = Column(DateTime, default=datetime.utcnow,
                                       onupdate=datetime.utcnow)
    notes_agent               = Column(Text, nullable=True)
    demandeur = relationship("Utilisateur",
                             back_populates="demandes_admissibilite")
    dossier   = relationship("Dossier", back_populates="demande_admissibilite",
                             uselist=False)


class Dossier(Base):
    __tablename__ = "dossiers"
    id                       = Column(Integer, primary_key=True, index=True)
    numero_dossier           = Column(String(25), unique=True, index=True)
    titre                    = Column(String(300), nullable=False)
    type_matiere             = Column(SAEnum(TypeMatiereJudiciaire), nullable=False)
    statut                   = Column(SAEnum(StatutDossier),
                                      default=StatutDossier.OUVERT)
    priorite                 = Column(Integer, default=2)
    description              = Column(Text)
    nom_client               = Column(String(200))
    nom_partie_adverse       = Column(String(200))
    assignee_id              = Column(Integer, ForeignKey("utilisateurs.id"),
                                      nullable=True)
    tribunal                 = Column(String(200),
                                      default="Cour du Québec – District de Longueuil")
    numero_greffe            = Column(String(50), nullable=True)
    date_ouverture           = Column(DateTime, default=datetime.utcnow)
    date_audience            = Column(DateTime, nullable=True)
    date_echeance            = Column(DateTime, nullable=True)
    date_cloture             = Column(DateTime, nullable=True)
    demande_admissibilite_id = Column(Integer,
                                      ForeignKey("demandes_admissibilite.id"),
                                      nullable=True)
    cree_le                  = Column(DateTime, default=datetime.utcnow)
    modifie_le               = Column(DateTime, default=datetime.utcnow,
                                      onupdate=datetime.utcnow)
    tags                     = Column(JSON, default=list)
    notes_internes           = Column(Text, nullable=True)
    assignee              = relationship("Utilisateur", back_populates="dossiers")
    demande_admissibilite = relationship("DemandeAdmissibilite",
                                         back_populates="dossier")
    documents             = relationship("Document", back_populates="dossier")
    transmissions         = relationship("Transmission", back_populates="dossier")
    historique            = relationship("HistoriqueDossier",
                                         back_populates="dossier",
                                         order_by="HistoriqueDossier.cree_le.desc()")


class HistoriqueDossier(Base):
    __tablename__ = "historique_dossiers"
    id         = Column(Integer, primary_key=True, index=True)
    dossier_id = Column(Integer, ForeignKey("dossiers.id", ondelete="CASCADE"),
                        nullable=False)
    auteur_id  = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    action     = Column(String(100), nullable=False)
    details    = Column(Text, nullable=True)
    cree_le    = Column(DateTime, default=datetime.utcnow)
    dossier    = relationship("Dossier", back_populates="historique")


class Document(Base):
    __tablename__ = "documents"
    id                     = Column(Integer, primary_key=True, index=True)
    numero_document        = Column(String(25), unique=True, index=True)
    dossier_id             = Column(Integer, ForeignKey("dossiers.id"), nullable=False)
    deposeur_id            = Column(Integer, ForeignKey("utilisateurs.id"),
                                    nullable=False)
    nom_fichier            = Column(String(300), nullable=False)
    nom_original           = Column(String(300), nullable=False)
    type_fichier           = Column(String(10))
    taille_octets          = Column(Integer)
    hash_sha256            = Column(String(64))
    chemin_stockage        = Column(String(500))
    categorie              = Column(String(100), default="Pièce justificative")
    description            = Column(Text, nullable=True)
    confidentiel           = Column(Boolean, default=False)
    statut                 = Column(SAEnum(StatutDocument),
                                    default=StatutDocument.DEPOSE)
    valide_par_id          = Column(Integer, ForeignKey("utilisateurs.id"),
                                    nullable=True)
    valide_le              = Column(DateTime, nullable=True)
    motif_rejet            = Column(Text, nullable=True)
    signe_electroniquement = Column(Boolean, default=False)
    empreinte_signature    = Column(String(128), nullable=True)
    cree_le                = Column(DateTime, default=datetime.utcnow)
    modifie_le             = Column(DateTime, default=datetime.utcnow,
                                    onupdate=datetime.utcnow)
    dossier    = relationship("Dossier", back_populates="documents")
    deposeur   = relationship("Utilisateur", back_populates="documents",
                              foreign_keys="[Document.deposeur_id]")
    valide_par = relationship("Utilisateur",
                              foreign_keys="[Document.valide_par_id]")

class Transmission(Base):
    __tablename__ = "transmissions"
    id                    = Column(Integer, primary_key=True, index=True)
    numero_transmission   = Column(String(25), unique=True, index=True)
    dossier_id            = Column(Integer, ForeignKey("dossiers.id"), nullable=False)
    initiateur_id         = Column(Integer, ForeignKey("utilisateurs.id"),
                                   nullable=False)
    greffe_destinataire   = Column(String(200),
                                   default="Greffe – District de Longueuil")
    email_greffe          = Column(String(200))
    documents_inclus      = Column(JSON, default=list)
    objet_transmission    = Column(String(500))
    message               = Column(Text, nullable=True)
    statut                = Column(SAEnum(StatutTransmission),
                                   default=StatutTransmission.EN_ATTENTE)
    envoye_le             = Column(DateTime, nullable=True)
    confirme_le           = Column(DateTime, nullable=True)
    accuse_reception      = Column(String(100), nullable=True)
    tentatives            = Column(Integer, default=0)
    erreur_detail         = Column(Text, nullable=True)
    protocole_chiffrement = Column(String(50), default="TLS 1.3 / AES-256")
    empreinte_paquet      = Column(String(64), nullable=True)
    cree_le               = Column(DateTime, default=datetime.utcnow)
    modifie_le            = Column(DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)
    dossier    = relationship("Dossier", back_populates="transmissions")
    initiateur = relationship("Utilisateur", back_populates="transmissions")


class JournalAudit(Base):
    __tablename__ = "journal_audit"
    id             = Column(Integer, primary_key=True, index=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    action         = Column(String(100), nullable=False)
    ressource      = Column(String(100))
    ressource_id   = Column(Integer, nullable=True)
    adresse_ip     = Column(String(45))
    details        = Column(JSON, nullable=True)
    cree_le        = Column(DateTime, default=datetime.utcnow)

