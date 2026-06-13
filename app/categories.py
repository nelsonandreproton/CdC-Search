"""Definição das categorias do diretório e mapeamento a partir dos tipos da Google.

A categorização tem duas fases:
  1. Determinística — mapeia o ``primaryType``/``types`` da Google para uma das
     nossas categorias (rápido, gratuito, fiável).
  2. LLM (fallback) — só é usada quando a fase 1 não chega a conclusão, para
     classificar a empresa a partir do nome + tipos. Ver ``app/ingest/llm.py``.
"""
from __future__ import annotations

# slug, nome, ícone, descrição, tipos-google associados
CATEGORIES: list[dict] = [
    {
        "slug": "restaurantes",
        "name": "Restaurantes",
        "icon": "🍽️",
        "description": "Restaurantes, take-away e refeições.",
        "google_types": ["restaurant", "meal_takeaway", "meal_delivery", "fast_food_restaurant"],
    },
    {
        "slug": "cafes-pastelarias",
        "name": "Cafés e Pastelarias",
        "icon": "☕",
        "description": "Cafés, pastelarias e casas de chá.",
        "google_types": ["cafe", "coffee_shop", "tea_house"],
    },
    {
        "slug": "padarias",
        "name": "Padarias",
        "icon": "🥖",
        "description": "Padarias e fabrico de pão.",
        "google_types": ["bakery"],
    },
    {
        "slug": "bares",
        "name": "Bares e Vida Noturna",
        "icon": "🍺",
        "description": "Bares, cervejarias e discotecas.",
        "google_types": ["bar", "pub", "night_club", "wine_bar"],
    },
    {
        "slug": "mercearias-supermercados",
        "name": "Mercearias e Supermercados",
        "icon": "🛒",
        "description": "Supermercados, mercearias e lojas de conveniência.",
        "google_types": ["supermarket", "grocery_store", "convenience_store", "market"],
    },
    {
        "slug": "talhos-peixarias",
        "name": "Talhos e Peixarias",
        "icon": "🥩",
        "description": "Talhos, peixarias e produtos frescos.",
        "google_types": ["butcher_shop", "seafood_market"],
    },
    {
        "slug": "farmacias-saude",
        "name": "Farmácias e Saúde",
        "icon": "💊",
        "description": "Farmácias, clínicas, médicos e dentistas.",
        "google_types": [
            "pharmacy",
            "drugstore",
            "doctor",
            "dentist",
            "hospital",
            "physiotherapist",
            "medical_lab",
            "clinic",
        ],
    },
    {
        "slug": "beleza-bem-estar",
        "name": "Beleza e Bem-estar",
        "icon": "💇",
        "description": "Cabeleireiros, estética, spas e ginásios.",
        "google_types": ["hair_salon", "beauty_salon", "nail_salon", "spa", "gym", "barber_shop"],
    },
    {
        "slug": "automovel",
        "name": "Automóvel",
        "icon": "🚗",
        "description": "Oficinas, stands, lavagens e combustível.",
        "google_types": ["car_repair", "car_dealer", "car_wash", "gas_station", "car_rental"],
    },
    {
        "slug": "lojas-comercio",
        "name": "Lojas e Comércio",
        "icon": "🛍️",
        "description": "Lojas de roupa, calçado, eletrónica, mobiliário e outros.",
        "google_types": [
            "store",
            "clothing_store",
            "shoe_store",
            "electronics_store",
            "furniture_store",
            "hardware_store",
            "book_store",
            "florist",
            "jewelry_store",
            "pet_store",
            "home_goods_store",
        ],
    },
    {
        "slug": "servicos",
        "name": "Serviços",
        "icon": "🏢",
        "description": "Bancos, seguros, imobiliárias, advogados e correios.",
        "google_types": [
            "bank",
            "atm",
            "insurance_agency",
            "real_estate_agency",
            "lawyer",
            "accounting",
            "post_office",
            "laundry",
            "travel_agency",
        ],
    },
    {
        "slug": "educacao",
        "name": "Educação",
        "icon": "🎓",
        "description": "Escolas, infantários e formação.",
        "google_types": ["school", "primary_school", "secondary_school", "university", "preschool"],
    },
    {
        "slug": "alojamento",
        "name": "Alojamento",
        "icon": "🏨",
        "description": "Hotéis, hospedagem e alojamento local.",
        "google_types": ["lodging", "hotel", "guest_house", "bed_and_breakfast"],
    },
    {
        "slug": "construcao-reparacoes",
        "name": "Construção e Reparações",
        "icon": "🔧",
        "description": "Canalizadores, eletricistas, pintores e empreiteiros.",
        "google_types": [
            "plumber",
            "electrician",
            "painter",
            "general_contractor",
            "roofing_contractor",
            "locksmith",
            "moving_company",
        ],
    },
    {
        "slug": "outros",
        "name": "Outros",
        "icon": "📍",
        "description": "Empresas ainda por categorizar.",
        "google_types": [],
    },
]

OUTROS_SLUG = "outros"

# Índice tipo-google -> slug da categoria (construído uma vez).
_TYPE_TO_SLUG: dict[str, str] = {}
for _cat in CATEGORIES:
    for _t in _cat["google_types"]:
        _TYPE_TO_SLUG[_t] = _cat["slug"]


def category_slugs() -> list[str]:
    return [c["slug"] for c in CATEGORIES]


def classify_by_google_types(types: list[str] | None) -> str | None:
    """Devolve o slug da categoria a partir dos tipos da Google, ou ``None``.

    Tenta os tipos pela ordem fornecida (o primeiro é o ``primaryType``).
    """
    if not types:
        return None
    for t in types:
        slug = _TYPE_TO_SLUG.get(t)
        if slug:
            return slug
    return None
