from __future__ import annotations

import re
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.offline_transfer import (
    OfflinePartUploadResponse,
    OfflineTransferManifest,
    OfflineTransferStatusResponse,
)
from app.security.offline_node import authenticate_offline_node
from app.services.offline_transfer_service import (
    TransferError,
    complete_transfer,
    create_transfer,
    get_transfer_for_node,
    receive_part,
    status_response,
)


router = APIRouter(prefix="/offline-transfer", tags=["offline-transfer"])
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _http_error(db: Session, exc: TransferError) -> HTTPException:
    db.rollback()
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.detail},
    )


@router.post(
    "/transfers",
    response_model=OfflineTransferStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_transfer(
    manifest: OfflineTransferManifest,
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> OfflineTransferStatusResponse:
    try:
        node = authenticate_offline_node(db, authorization)
        transfer, created = create_transfer(db, node, manifest)
        if not created:
            response.status_code = status.HTTP_200_OK
        return status_response(db, transfer)
    except TransferError as exc:
        raise _http_error(db, exc) from exc


@router.get(
    "/transfers/{transfer_id}",
    response_model=OfflineTransferStatusResponse,
)
def get_transfer(
    transfer_id: UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> OfflineTransferStatusResponse:
    try:
        node = authenticate_offline_node(db, authorization)
        transfer = get_transfer_for_node(db, node, transfer_id)
        return status_response(db, transfer)
    except TransferError as exc:
        raise _http_error(db, exc) from exc


@router.get(
    "/transfers/{transfer_id}/status",
    response_model=OfflineTransferStatusResponse,
)
def get_transfer_status(
    transfer_id: UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> OfflineTransferStatusResponse:
    return get_transfer(transfer_id, authorization, db)


@router.put(
    "/transfers/{transfer_id}/parts/{part_number}",
    response_model=OfflinePartUploadResponse,
)
async def put_transfer_part(
    transfer_id: UUID,
    part_number: int,
    request: Request,
    authorization: str | None = Header(default=None),
    x_part_offset: int | None = Header(default=None, alias="X-Part-Offset"),
    x_part_sha256: str = Header(alias="X-Part-SHA256"),
    content_length: int = Header(alias="Content-Length"),
    db: Session = Depends(get_db),
) -> OfflinePartUploadResponse:
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != (
        "application/octet-stream"
    ):
        raise HTTPException(status_code=415, detail="expected application/octet-stream")
    if content_length <= 0:
        raise HTTPException(status_code=400, detail="Content-Length must be positive")
    if not _SHA256_RE.fullmatch(x_part_sha256):
        raise HTTPException(status_code=422, detail="X-Part-SHA256 must be lowercase hex")

    try:
        node = authenticate_offline_node(db, authorization)
        return await receive_part(
            db,
            node,
            transfer_id,
            part_number,
            byte_offset=x_part_offset,
            content_length=content_length,
            part_sha256=x_part_sha256,
            body=request.stream(),
        )
    except TransferError as exc:
        raise _http_error(db, exc) from exc


@router.post(
    "/transfers/{transfer_id}/complete",
    response_model=OfflineTransferStatusResponse,
    status_code=status.HTTP_200_OK,
)
def finish_transfer(
    transfer_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> OfflineTransferStatusResponse:
    try:
        node = authenticate_offline_node(db, authorization)
        transfer = complete_transfer(db, node, transfer_id)
        return status_response(db, transfer)
    except TransferError as exc:
        raise _http_error(db, exc) from exc
