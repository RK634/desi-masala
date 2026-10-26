
import os
import traceback

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import get_connection
from auth import router as auth_router
from commerce import router as commerce_router
from support import router as support_router
from engagement import router as engagement_router


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(title="Desi Masala API")


# --------------------------------------------------
# CORS Configuration
# --------------------------------------------------

allowed_origins = [
    "https://desi-masala-lovat.vercel.app",
]

# Allow the local Vite frontend during development.
if os.getenv("ENVIRONMENT", "").lower() != "production":
    allowed_origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# API Routers
# --------------------------------------------------

app.include_router(auth_router)
app.include_router(commerce_router)
app.include_router(support_router)
app.include_router(engagement_router)


# --------------------------------------------------
# Root Endpoint
# --------------------------------------------------

@app.get("/")
def home():
    return {"message": "Desi Masala API is running"}


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/health")
def health():
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")

        return {
            "status": "healthy",
            "database": "connected",
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )


# --------------------------------------------------
# Get Products
# --------------------------------------------------

@app.get("/products")
def get_products(language: str = "en"):
    """
    Return active products with approved translations.
    Fall back to the original product data when a
    translation is unavailable.
    """

    language = language.lower().strip()

    supported_languages = {"en", "de", "fr", "es", "pl", "hi"}

    if language not in supported_languages:
        raise HTTPException(
            status_code=400,
            detail="Unsupported language",
        )

    query = """
        SELECT
            p.id,
            COALESCE(pt.name, p.name) AS name,
            p.price,
            p.brand,
            COALESCE(pt.description, p.description) AS description,
            COALESCE(pt.category_name, p.category) AS category,
            p.image_url,
            GREATEST(
                p.discount_percent,
                COALESCE(p.expiry_discount_percent, 0)
            ) AS discount_percent,
            p.is_featured,
            p.is_new_arrival,
            COALESCE(SUM(i.quantity), 0) AS stock_quantity
        FROM public.products p
        LEFT JOIN public.product_translations pt
            ON pt.product_id = p.id
            AND pt.language_code = %s
            AND (pt.reviewed = TRUE OR %s = 'en')
        LEFT JOIN public.inventory i
            ON i.product_id = p.id
        WHERE p.active = TRUE
        GROUP BY
            p.id,
            pt.name,
            pt.description,
            pt.category_name
        ORDER BY COALESCE(pt.name, p.name);
    """

    try:
        with get_connection() as conn:
            rows = conn.execute(
                query,
                (language, language),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "price": float(row["price"]),
                "brand": row["brand"],
                "description": row["description"],
                "category": row["category"],
                "image_url": row["image_url"],
                "discount_percent": float(
                    row["discount_percent"] or 0
                ),
                "is_featured": row["is_featured"],
                "is_new_arrival": row["is_new_arrival"],
                "stock_quantity": row["stock_quantity"],
            }
            for row in rows
        ]

    except Exception:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve products",
        )
