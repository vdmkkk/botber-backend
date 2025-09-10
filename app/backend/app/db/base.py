# Re-export Base and ensure all models are imported so metadata is complete
from app.db.session import Base  # provides Base.metadata

# Import models here so Alembic can discover them via Base.metadata
from app.models.user import User  # noqa: F401
from app.models.bot import Bot  # noqa: F401
from app.models.bot_instance import UserBotInstance  # noqa: F401
from app.models.verification import EmailVerification  # noqa: F401
from app.models.password_reset import PasswordReset  # noqa: F401
from app.models.enums import InstanceStatus  # noqa: F401
