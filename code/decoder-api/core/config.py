import os

DAV1D_PATH = os.environ.get("DAV1D_PATH", "")
REDIS_URL = os.environ["REDIS_URL"]
MAX_CONCURRENT = (os.cpu_count() or 4) * 2