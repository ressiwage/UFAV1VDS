from _shared._common.db.relational import get_db, get_db_
from _shared._common.db.redis import redis_client
from _shared._common.db.s3 import s3


def get_redis():
    return redis_client

