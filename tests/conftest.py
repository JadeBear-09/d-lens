import os

os.environ["DATABASE_URL"] = "sqlite:///./test_dlens.db"
os.environ["QDRANT_URL"] = ""
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["OPENAI_API_KEY"] = ""
