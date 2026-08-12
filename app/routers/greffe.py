import hashlib, uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.database import get_db, SessionLocal

router = APIRouter(prefix="/api/greffe", tags=["Greffe"])


async def simuler_envoi(transmission_id: int):
    import asyncio, random
    await asyncio.sleep(2)
    db = SessionLocal()
    try:
        t = db.query(models.Transmission).filter(
            models.Transmission.id == transmission_id
        ).first()
        if not t:
            return
        t.tentatives += 1
        t.envoye_le   = datetime.utcnow()
        if random.random() > 0.03:
            t.statut           = models.StatutTransmission.CONFIRME
            t.accuse_reception = (
                f"AR-{t.numero_transmission}-{uuid.uuid4().hex[:8].upper()}"
            )
            t.confirme_le = datetime.utcnow()
        else:
            t.statut        = models.StatutTransmission.ECHEC
            t.erreur_detail = "Connexion au greffe temporairement indisponible"
        db.commit()
    finally:
        db.close()


@router.post("/", response_model=schemas.TransmissionPublic, status_code=201)
def transmettre(
    data: schemas.TransmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
        models.RoleUtilisateur.AVOCAT, models.RoleUtilisateur.AGENT_AJ,
    )),
):
    dossier = db.query(models.Dossier).filter(
        models.Dossier.id == data.dossier_id
    ).first()
    if not dossier:
        raise HTTPException(404, "Dossier introuvable")

    count  = db.query(models.Transmission).count() + 1
    numero = f"TRX-{datetime.utcnow().year}-{count:05d}"

    empreinte = hashlib.sha256(
        f"{numero}:{data.documents_ids}:{datetime.utcnow().isoformat()}"
        .encode()
    ).hexdigest()

    transmission = models.Transmission(
        numero_transmission=numero,
        dossier_id=data.dossier_id,
        initiateur_id=current_user.id,
        greffe_destinataire=data.greffe_destinataire,
        email_greffe=data.email_greffe,
        objet_transmission=data.objet_transmission,
        message=data.message,
        documents_inclus=data.documents_ids,
        statut=models.StatutTransmission.EN_ATTENTE,
        protocole_chiffrement="TLS 1.3 / AES-256",
        empreinte_paquet=empreinte,
    )
    db.add(transmission)
    db.add(models.HistoriqueDossier(
        dossier_id=data.dossier_id,
        auteur_id=current_user.id,
        action="TRANSMISSION_INITIEE",
        details=f"Transmission {numero} vers {data.greffe_destinataire}",
    ))
    db.commit()
    db.refresh(transmission)
    background_tasks.add_task(simuler_envoi, transmission.id)
    return transmission


@router.get("/stats/resume")
def stats(
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    total     = db.query(models.Transmission).count()
    confirmes = db.query(models.Transmission).filter(
        models.Transmission.statut == models.StatutTransmission.CONFIRME
    ).count()
    echecs    = db.query(models.Transmission).filter(
        models.Transmission.statut == models.StatutTransmission.ECHEC
    ).count()
    attente   = db.query(models.Transmission).filter(
        models.Transmission.statut == models.StatutTransmission.EN_ATTENTE
    ).count()
    taux = round(confirmes / total * 100 if total > 0 else 0.0, 2)
    return {
        "total": total, "confirmees": confirmes,
        "echecs": echecs, "en_attente": attente,
        "taux_succes_pct": taux, "objectif_pilote_pct": 99.0,
    }


@router.get("/", response_model=list[schemas.TransmissionPublic])
def lister(
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
    dossier_id: int = Query(None),
    statut: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    if current_user.role == models.RoleUtilisateur.CITOYEN:
        raise HTTPException(403, "Accès refusé")
    q = db.query(models.Transmission)
    if dossier_id: q = q.filter(models.Transmission.dossier_id == dossier_id)
    if statut:     q = q.filter(models.Transmission.statut == statut)
    return (q.order_by(models.Transmission.cree_le.desc())
             .offset((page - 1) * per_page).limit(per_page).all())


@router.get("/{transmission_id}", response_model=schemas.TransmissionPublic)
def detail(
    transmission_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.get_utilisateur_courant),
):
    t = db.query(models.Transmission).filter(
        models.Transmission.id == transmission_id
    ).first()
    if not t:
        raise HTTPException(404, "Transmission introuvable")
    return t


@router.post("/{transmission_id}/retransmettre",
             response_model=schemas.TransmissionPublic)
def retransmettre(
    transmission_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    t = db.query(models.Transmission).filter(
        models.Transmission.id == transmission_id
    ).first()
    if not t:
        raise HTTPException(404, "Transmission introuvable")
    if t.statut != models.StatutTransmission.ECHEC:
        raise HTTPException(422, "Seules les transmissions en échec peuvent être relancées")
    if t.tentatives >= 5:
        raise HTTPException(422, "Nombre maximum de tentatives atteint (5)")
    t.statut        = models.StatutTransmission.EN_ATTENTE
    t.erreur_detail = None
    db.commit()
    db.refresh(t)
    background_tasks.add_task(simuler_envoi, t.id)
    return t
