from _shared._common.db.relational import get_db, get_db_
from _shared._common.db.redis import redis_client

def get_redis():
    return redis_client

