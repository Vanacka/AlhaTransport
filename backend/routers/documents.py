import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user, require_admin
from models import User, UserRole, Document
from schemas import DocumentCreate, DocumentUpdate, DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _document_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        file_path=doc.file_path,
        file_name=doc.file_name,
        visible_to_all=doc.visible_to_all,
        visible_user_ids=[u.id for u in doc.visible_to_users],
        position=doc.position,
        created_by_id=doc.created_by_id,
        created_by_name=doc.created_by.full_name,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _get_document_or_404(db: Session, document_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Dokument nenalezen")
    return doc


def _set_visible_users(db: Session, doc: Document, user_ids: list[int]) -> None:
    doc.visible_to_users = (
        db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Admin vidí vše, kurýr jen dokumenty pro všechny nebo výslovně pro něj."""
    q = db.query(Document)
    if current_user.role != UserRole.admin:
        q = q.filter(
            or_(
                Document.visible_to_all == True,  # noqa: E712
                Document.visible_to_users.any(User.id == current_user.id),
            )
        )
    docs = q.order_by(Document.position, Document.created_at.desc()).all()
    return [_document_out(d) for d in docs]


@router.post("", response_model=DocumentOut)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    doc = Document(
        title=payload.title,
        content=payload.content,
        visible_to_all=payload.visible_to_all,
        created_by_id=current_user.id,
    )
    db.add(doc)
    db.flush()
    if not payload.visible_to_all:
        _set_visible_users(db, doc, payload.visible_user_ids)
    db.commit()
    db.refresh(doc)
    return _document_out(doc)


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doc = _get_document_or_404(db, document_id)
    if payload.title is not None:
        doc.title = payload.title
    if payload.content is not None:
        doc.content = payload.content
    if payload.visible_to_all is not None:
        doc.visible_to_all = payload.visible_to_all
    if payload.visible_user_ids is not None:
        _set_visible_users(db, doc, payload.visible_user_ids)
    if payload.position is not None:
        doc.position = payload.position
    db.commit()
    db.refresh(doc)
    return _document_out(doc)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doc = _get_document_or_404(db, document_id)
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.post("/{document_id}/file", response_model=DocumentOut)
async def upload_document_file(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doc = _get_document_or_404(db, document_id)
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(await file.read())

    doc.file_path = path
    doc.file_name = file.filename
    db.commit()
    db.refresh(doc)
    return _document_out(doc)


@router.delete("/{document_id}/file", response_model=DocumentOut)
def delete_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doc = _get_document_or_404(db, document_id)
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    doc.file_path = None
    doc.file_name = None
    db.commit()
    db.refresh(doc)
    return _document_out(doc)
