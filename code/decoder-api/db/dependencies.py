from _shared._common.db.relational import get_db
from _shared._common.db.redis import redis_client

def get_redis():
    return redis_client