from app.models.role import ProductType
from app.modules.shared.product_router import ProductRouterConfig, create_product_router
from app.security.rbac import SMALL_READ_ROLES, SMALL_WRITE_ROLES

router = create_product_router(
    ProductRouterConfig(
        product_type=ProductType.SMALL,
        read_roles=SMALL_READ_ROLES,
        write_roles=SMALL_WRITE_ROLES,
        tags=["Small Lagoons"],
        include_tag_write_endpoint=True,
    )
)
