from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/admissibilite", tags=["Admissibilité"])


def evaluer(demande: models.DemandeAdmissibilite) -> schemas.ResultatEvaluation:
    """Moteur de scoring automatisé 0-100."""

    if demande.beneficiaire_aide_sociale:
        return schemas.ResultatEvaluation(
            statut=models.StatutAdmissibilite.ADMISSIBLE,
            score=100.0, admissible=True,
            motif="Admission automatique – bénéficiaire aide sociale",
            seuil_revenu_applicable=0.0,
            details={"raison": "aide_sociale"},
        )

    seuil = (settings.SEUIL_REVENU_1_PERSONNE
             + demande.nb_personnes_charge * settings.SEUIL_REVENU_PAR_CHARGE)
    score = 0.0

    # Critère revenu (0-50 pts)
    if demande.revenu_annuel <= seuil:
        ratio = 1 - (demande.revenu_annuel / seuil)
        score += min(50.0, 50.0 * (1 + ratio))
    else:
        depassement = (demande.revenu_annuel - seuil) / seuil
        score += max(0.0, 50.0 - depassement * 100)

    # Critère actif (0-30 pts)
    if demande.actif_total <= settings.SEUIL_ACTIF_MAX:
        ratio_a = 1 - (demande.actif_total / settings.SEUIL_ACTIF_MAX)
        score += 30.0 * (0.5 + 0.5 * ratio_a)

    # Bonus charges (0-10 pts)
    score += min(10.0, demande.nb_personnes_charge * 2.0)

    # Bonus matières prioritaires (0-10 pts)
    if demande.type_matiere in [
        models.TypeMatiereJudiciaire.FAMILIAL,
        models.TypeMatiereJudiciaire.LOGEMENT,
        models.TypeMatiereJudiciaire.PENAL_MINEUR,
    ]:
        score += 10.0

    score = round(min(100.0, score), 2)
    revenu_ok = demande.revenu_annuel <= seuil
    actif_ok  = demande.actif_total <= settings.SEUIL_ACTIF_MAX

    if revenu_ok and actif_ok and score >= 50.0:
        return schemas.ResultatEvaluation(
            statut=models.StatutAdmissibilite.ADMISSIBLE,
            score=score, admissible=True,
            motif=f"Admissible (score {score}/100) – critères satisfaits",
            seuil_revenu_applicable=seuil,
            details={"seuil": seuil},
        )
    elif score < 30.0:
        return schemas.ResultatEvaluation(
            statut=models.StatutAdmissibilite.NON_ADMISSIBLE,
            score=score, admissible=False,
            motif=f"Non admissible (score {score}/100) – revenu dépasse le seuil",
            seuil_revenu_applicable=seuil,
            details={"seuil": seuil},
        )
    else:
        return schemas.ResultatEvaluation(
            statut=models.StatutAdmissibilite.REVISION,
            score=score, admissible=False,
            motif=f"Révision manuelle requise (score {score}/100)",
            seuil_revenu_applicable=seuil,
            details={"seuil": seuil},
        )


@router.post("/", response_model=schemas.DemandeAdmissibilitePublic, status_code=201)
def soumettre(
    data: schemas.DemandeAdmissibiliteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
):
    count = db.query(models.DemandeAdmissibilite).count() + 1
    demande = models.DemandeAdmissibilite(
        numero_demande=f"AJ-{datetime.utcnow().year}-{count:05d}",
        demandeur_id=current_user.id,
        **data.model_dump(),
    )
    db.add(demande)
    db.flush()
    r = evaluer(demande)
    demande.statut               = r.statut
    demande.score_admissibilite  = r.score
    demande.motif_decision       = r.motif
    demande.evalue_automatiquement = True
    demande.evalue_le            = datetime.utcnow()
    db.commit()
    db.refresh(demande)
    return demande


@router.get("/stats/resume")
def stats(
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN,
        models.RoleUtilisateur.AGENT_AJ,
        models.RoleUtilisateur.GREFFIER,
    )),
):
    total = db.query(models.DemandeAdmissibilite).count()
    adm   = db.query(models.DemandeAdmissibilite).filter(
        models.DemandeAdmissibilite.statut == models.StatutAdmissibilite.ADMISSIBLE
    ).count()
    non   = db.query(models.DemandeAdmissibilite).filter(
        models.DemandeAdmissibilite.statut == models.StatutAdmissibilite.NON_ADMISSIBLE
    ).count()
    rev   = db.query(models.DemandeAdmissibilite).filter(
        models.DemandeAdmissibilite.statut == models.StatutAdmissibilite.REVISION
    ).count()
    auto  = db.query(models.DemandeAdmissibilite).filter(
        models.DemandeAdmissibilite.evalue_automatiquement == True
    ).count()
    taux  = round(auto / total * 100 if total > 0 else 0.0, 2)
    return {
        "total": total, "admissibles": adm,
        "non_admissibles": non, "en_revision": rev,
        "evaluations_automatiques": auto,
        "taux_automatisation_pct": taux,
        "objectif_pilote_pct": 80.0,
        "objectif_atteint": taux >= 80.0,
    }


@router.get("/", response_model=list[schemas.DemandeAdmissibilitePublic])
def lister(
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
    statut: str = Query(None),
    type_matiere: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    q = db.query(models.DemandeAdmissibilite)
    if current_user.role == models.RoleUtilisateur.CITOYEN:
        q = q.filter(
            models.DemandeAdmissibilite.demandeur_id == current_user.id
        )
    if statut:       q = q.filter(models.DemandeAdmissibilite.statut == statut)
    if type_matiere: q = q.filter(
        models.DemandeAdmissibilite.type_matiere == type_matiere
    )
    return (q.order_by(models.DemandeAdmissibilite.cree_le.desc())
             .offset((page - 1) * per_page).limit(per_page).all())


@router.get("/{demande_id}", response_model=schemas.DemandeAdmissibilitePublic)
def detail(
    demande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
):
    d = db.query(models.DemandeAdmissibilite).filter(
        models.DemandeAdmissibilite.id == demande_id
    ).first()
    if not d:
        raise HTTPException(404, "Demande introuvable")
    if (current_user.role == models.RoleUtilisateur.CITOYEN
            and d.demandeur_id != current_user.id):
        raise HTTPException(403, "Accès refusé")
    return d
