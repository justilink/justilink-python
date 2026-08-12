import hashlib, os, uuid
from datetime import datetime
from fastapi import (APIRouter, Depends, HTTPException,
                     UploadFile, File, Form, Query)
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/documents", tags=["Documents"])
UPLOAD_DIR = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/", response_model=schemas.DocumentPublic, status_code=201)
async def deposer(
    dossier_id:   int  = Form(...),
    categorie:    str  = Form("Pièce justificative"),
    description:  str  = Form(None),
    confidentiel: bool = Form(False),
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_utilisateur_courant),
):
    ext = fichier.filename.rsplit(".", 1)[-1].lower() if "." in fichier.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(422, f"Extension non autorisée : .{ext}")

    contenu   = await fichier.read()
    taille_mb = len(contenu) / (1024 * 1024)
    if taille_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(413, f"Fichier trop volumineux ({taille_mb:.1f} Mo)")

    dossier = db.query(models.Dossier).filter(
        models.Dossier.id == dossier_id
    ).first()
    if not dossier:
        raise HTTPException(404, "Dossier introuvable")
    if dossier.statut == models.StatutDossier.CLOTURE:
        raise HTTPException(422, "Dossier clôturé – dépôt impossible")

    hash_sha256 = hashlib.sha256(contenu).hexdigest()
    doublon = db.query(models.Document).filter(
        models.Document.dossier_id == dossier_id,
        models.Document.hash_sha256 == hash_sha256,
    ).first()
    if doublon:
        raise HTTPException(409, f"Document déjà déposé ({doublon.numero_document})")

    nom_stockage = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(UPLOAD_DIR, nom_stockage), "wb") as f:
        f.write(contenu)

    empreinte = hashlib.sha256(
        f"{current_user.email}:{hash_sha256}:{datetime.utcnow().isoformat()}"
        .encode()
    ).hexdigest()

    count = db.query(models.Document).count() + 1
    doc = models.Document(
        numero_document=f"DOC-{datetime.utcnow().year}-{count:05d}",
        dossier_id=dossier_id, deposeur_id=current_user.id,
        nom_fichier=nom_stockage, nom_original=fichier.filename,
        type_fichier=ext, taille_octets=len(contenu),
        hash_sha256=hash_sha256,
        chemin_stockage=os.path.join(UPLOAD_DIR, nom_stockage),
        categorie=categorie, description=description,
        confidentiel=confidentiel,
        statut=models.StatutDocument.DEPOSE,
        signe_electroniquement=True, empreinte_signature=empreinte,
    )
    db.add(doc)
    db.add(models.HistoriqueDossier(
        dossier_id=dossier_id, auteur_id=current_user.id,
        action="DOCUMENT_DEPOSE",
        details=f"'{fichier.filename}' ({taille_mb:.2f} Mo)",
    ))
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/stats/resume")
def stats(
    db: Session = Depends(get_db),
    _=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    total = db.query(models.Document).count()
    par_statut = {
        s.value: db.query(models.Document).filter(
            models.Document.statut == s
        ).count()
        for s in models.StatutDocument
    }
    return {"total": total, "par_statut": par_statut}


@router.get("/", response_model=list[schemas.DocumentPublic])
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
    q = db.query(models.Document)
    if dossier_id: q = q.filter(models.Document.dossier_id == dossier_id)
    if statut:     q = q.filter(models.Document.statut == statut)
    return (q.order_by(models.Document.cree_le.desc())
             .offset((page - 1) * per_page).limit(per_page).all())


@router.patch("/{doc_id}/valider", response_model=schemas.DocumentPublic)
def valider(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    doc = db.query(models.Document).filter(
        models.Document.id == doc_id
    ).first()
    if not doc: raise HTTPException(404, "Document introuvable")
    doc.statut        = models.StatutDocument.VALIDE
    doc.valide_par_id = current_user.id
    doc.valide_le     = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    return doc


@router.patch("/{doc_id}/rejeter", response_model=schemas.DocumentPublic)
def rejeter(
    doc_id: int,
    motif: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
    current_user=Depends(auth.exiger_role(
        models.RoleUtilisateur.ADMIN, models.RoleUtilisateur.GREFFIER,
    )),
):
    doc = db.query(models.Document).filter(
        models.Document.id == doc_id
    ).first()
    if not doc: raise HTTPException(404, "Document introuvable")
    doc.statut        = models.StatutDocument.REJETE
    doc.motif_rejet   = motif
    doc.valide_par_id = current_user.id
    doc.valide_le     = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{doc_id}/verifier-integrite")
def verifier(
    doc_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.get_utilisateur_courant),
):
    doc = db.query(models.Document).filter(
        models.Document.id == doc_id
    ).first()
    if not doc: raise HTTPException(404, "Document introuvable")
    if not os.path.exists(doc.chemin_stockage):
        return {"integrite": False, "erreur": "Fichier physique introuvable"}
    with open(doc.chemin_stockage, "rb") as f:
        hash_actuel = hashlib.sha256(f.read()).hexdigest()
    return {
        "document_id": doc.id,
        "numero_document": doc.numero_document,
        "integrite": hash_actuel == doc.hash_sha256,
        "hash_reference": doc.hash_sha256,
        "hash_actuel": hash_actuel,
        "verifie_le": datetime.utcnow().isoformat(),
    }
