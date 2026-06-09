from app.models.role import ProductType
from app.modules.shared.product_router import ProductRouterConfig, create_product_router
from app.security.rbac import CRYSTAL_READ_ROLES, CRYSTAL_WRITE_ROLES

router = create_product_router(
    ProductRouterConfig(
        product_type=ProductType.CRYSTAL,
        read_roles=CRYSTAL_READ_ROLES,
        write_roles=CRYSTAL_WRITE_ROLES,
        tags=["Crystal"],
    )
)
