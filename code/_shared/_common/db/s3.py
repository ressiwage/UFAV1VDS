import boto3
from botocore.client import Config

import os

def read_secret(name: str) -> str:
    """Читает секрет из /run/secrets/, fallback на env (для локальной разработки)."""
    secret_path = f"/run/secrets/env"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            parsed = {i.split('=')[0]:i.split('=')[-1] for i in f.read().strip().split('\n')}
            print(parsed)
            return parsed[name]
    
    raise RuntimeError(f"Secret '{name}' not found in {secret_path} or env")

# from _shared._common.db.s3_config import S3_BUCKET_NAME, S3_ACCESS_TOKEN, S3_SECRET_TOKEN

s3 = boto3.client(
    's3',
    endpoint_url='https://s3.twcstorage.ru',
    aws_access_key_id=read_secret('S3_ACCESS_TOKEN'),
    aws_secret_access_key=('S3_SECRET_TOKEN'),
    config=Config(signature_version='s3v4'),
        region_name='ru-1' 

)