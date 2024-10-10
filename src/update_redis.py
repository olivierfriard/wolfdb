"""
update redis with WA loci values

This script is required by wolfdb.py

"""

import sys
import redis

from config import config

from update_redis_with_wa_loci_values import update_redis_wa_loci
from update_redis_with_genotypes_loci_values import update_redis_genotypes_loci

params = config()
if not params:
    print("Parameters not found")
    sys.exit(1)

# dev version use db #1
rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))

# empty db
rdis.flushdb()


if __name__ == "__main__":
    update_redis_wa_loci()
    update_redis_genotypes_loci()
