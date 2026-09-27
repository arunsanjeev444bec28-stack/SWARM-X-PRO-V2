# Forward imports for the top-level intelligence package
# This allows imports like "from intelligence.dataset import generate_episode"
# to resolve to the implementation under backend/intelligence.

from backend.intelligence import *  # noqa: F403,F401
