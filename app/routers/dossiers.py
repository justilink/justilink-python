from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.database import get_db

router = APIRouter(prefix="/api/dossiers", tags=["Dossiers"])


def ajouter_historique(db, dossier_id, auteur_id, action, details=None):
    db.add(models.HistoriqueDossier(
        dossier_id=dossier_id, auteur_id=auteur_id,
        action=action, details=details,
    ))


@router.post("/", response_model=schemas.DossierPublic, status_code=201)
def creer(
    data: schemas.DossierCreate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
        models.RoleUtilisateur.AVOCAT, models.RoleUtilisateur.AGENT_AJ,
    )),
):
    count = db.query(models.Dossier).count() + 1
    dossier = models.Dossier(
        numero_dossier=f"DOS-{datetime.utcnow().year}-{count:05d}",
        assignee_id=current_user.id,
        **data.model_dump(),
    )
    db.add(dossier)
    db.flush()
    ajouter_historique(db, dossier.id, current_user.id,
                       "OUVERTURE",
                       f"Dossier ouvert par {current_user.nom_complet}")
    db.commit()
    db.refresh(dossier)
    return dossier


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    total = db.query(models.Dossier).count()
    par_statut = {
        s.value: db.query(models.Dossier).filter(
            models.Dossier.statut == s
        ).count()
        for s in models.StatutDossier
    }
    urgents = db.query(models.Dossier).filter(
        models.Dossier.priorite == 1,
        models.Dossier.statut.in_([
            models.StatutDossier.OUVERT,
            models.StatutDossier.EN_COURS,
        ]),
    ).count()
    return {"total": total, "par_statut": par_statut,
            "dossiers_urgents_actifs": urgents}


@router.get("/", response_model=list[schemas.DossierPublic])
def lister(
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
    statut: str = Query(None),
    priorite: int = Query(None),
    q: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    if current_user.role == models.RoleUtilisateur.CITOYEN:
        raise HTTPException(403, "Accès réservé au personnel judiciaire")
    query = db.query(models.Dossier)
    if current_user.role == models.RoleUtilisateur.AVOCAT:
        query = query.filter(models.Dossier.assignee_id == current_user.id)
    if statut:   query = query.filter(models.Dossier.statut == statut)
    if priorite: query = query.filter(models.Dossier.priorite == priorite)
    if q:
        like = f"%{q}%"
        query = query.filter(
            models.Dossier.titre.ilike(like) |
            models.Dossier.nom_client.ilike(like)
        )
    return (query
            .order_by(models.Dossier.priorite.asc(),
                      models.Dossier.cree_le.desc())
            .offset((page - 1) * per_page).limit(per_page).all())


@router.get("/{dossier_id}", response_model=schemas.DossierDetail)
def detail(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
):
    if current_user.role == models.RoleUtilisateur.CITOYEN:
        raise HTTPException(403, "Accès refusé")
    d = db.query(models.Dossier).filter(
        models.Dossier.id == dossier_id
    ).first()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    result = schemas.DossierDetail.model_validate(d)
    result.nb_documents     = len(d.documents)
    result.nb_transmissions = len(d.transmissions)
    return result


@router.patch("/{dossier_id}", response_model=schemas.DossierPublic)
def modifier(
    dossier_id: int,
    data: schemas.DossierUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
        models.RoleUtilisateur.AVOCAT, models.RoleUtilisateur.AGENT_AJ,
    )),
):
    d = db.query(models.Dossier).filter(
        models.Dossier.id == dossier_id
    ).first()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    changements = []
    for field, value in data.model_dump(exclude_none=True).items():
        if getattr(d, field) != value:
            changements.append(f"{field} modifié")
            setattr(d, field, value)
    if data.statut == models.StatutDossier.CLOTURE and not d.date_cloture:
        d.date_cloture = datetime.utcnow()
    if changements:
        ajouter_historique(db, dossier_id, current_user.id,
                           "MODIFICATION", " | ".join(changements))
    db.commit()
    db.refresh(d)
    return d


@router.get("/{dossier_id}/historique",
            response_model=list[schemas.HistoriquePublic])
def historique(
    dossier_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.get_utilisateur_courant),
):
    return (db.query(models.HistoriqueDossier)
              .filter(models.HistoriqueDossier.dossier_id == dossier_id)
              .order_by(models.HistoriqueDossier.cree_le.desc()).all())


@router.delete("/{dossier_id}", response_model=schemas.MessageResponse)
def cloturer(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    d = db.query(models.Dossier).filter(
        models.Dossier.id == dossier_id
    ).first()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    d.statut       = models.StatutDossier.CLOTURE
    d.date_cloture = datetime.utcnow()
    ajouter_historique(db, dossier_id, current_user.id,
                       "CLOTURE", f"Clôturé par {current_user.nom_complet}")
    db.commit()
    return schemas.MessageResponse(
        message=f"Dossier {d.numero_dossier} clôturé avec succès"
    )
