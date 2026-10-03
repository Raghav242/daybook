import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://daybook:daybook_local@localhost:5432/daybook"
)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
