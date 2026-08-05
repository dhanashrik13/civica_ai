import os
import json
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class SecretManager:
    """
    Enterprise Secret Management Abstraction.
    Supports: Environment Variables, AWS Secrets Manager, Local Mock.
    """
    
    @staticmethod
    @lru_cache()
    def get_secret(secret_name, default=None):
        # 1. Try Environment Variable (Override)
        val = os.getenv(secret_name)
        if val:
            return val
            
        # 2. Try AWS Secrets Manager (Mocked implementation for this phase)
        # In real prod: use boto3.client('secretsmanager').get_secret_value(...)
        if os.getenv("USE_AWS_SECRETS") == "True":
            try:
                # Logic to fetch from AWS would go here
                pass
            except Exception as e:
                logger.error(f"Failed to fetch secret {secret_name} from AWS: {str(e)}")

        return default

    @classmethod
    def get_db_config(cls):
        """Returns DB config from secrets or env."""
        db_url = cls.get_secret("DATABASE_URL")
        if db_url:
            return db_url
        
        # Fallback to discrete parts
        user = cls.get_secret("DB_USER", "postgres")
        password = cls.get_secret("DB_PASSWORD", "postgres_password")
        host = cls.get_secret("DB_HOST", "db")
        port = cls.get_secret("DB_PORT", "5432")
        name = cls.get_secret("DB_NAME", "civica_db")
        
        return f"postgres://{user}:{password}@{host}:{port}/{name}"

def get_secret(name, default=None):
    return SecretManager.get_secret(name, default)
