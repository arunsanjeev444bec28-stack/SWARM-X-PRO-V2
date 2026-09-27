# This package forwards imports to the actual implementation under backend/models
# It enables imports like "from models.schemas import ..." to work.

from backend.models.schemas import *  # noqa: F403,F401
