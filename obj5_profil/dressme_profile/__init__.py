"""DressMe — objectif 5 : profil de style (contrat StyleProfile v1)."""
from .contracts import ItemCard, ProfileRequest, RecommendRequest, StyleProfile
from .service import ProfileService, load_items

__all__ = ["ItemCard", "StyleProfile", "ProfileRequest", "RecommendRequest",
           "ProfileService", "load_items"]
__version__ = "1.0.0"
