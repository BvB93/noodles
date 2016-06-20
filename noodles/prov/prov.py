from tinydb import (TinyDB, Query)
import hashlib
import json
from threading import Lock
# from ..utility import on
import time
import uuid
import sys


def update_object_hash(m, obj):
    r = json.dumps(obj, sort_keys=True)
    m.update(r.encode())
    return m


def prov_key(job_msg):
    """Retrieves a MD5 sum from a function call. This takes into account the
    name of the function, the arguments and possibly a version number of the
    function, if that is given in the hints. 
    This version can also be auto-generated by generating an MD5 hash from the
    function source. However, the source-code may not always be reachable, or
    the result may depend on an external process which has its own versioning."""
    m = hashlib.md5()
    update_object_hash(m, job_msg['data']['function'])
    update_object_hash(m, job_msg['data']['arguments'])

    if 'version' in job_msg['data']['hints']:
        update_object_hash(m, job_msg['data']['hints']['version'])

    return m.hexdigest()


def time_stamp():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time()))
   

def attach_job(key):
    def attach_to(rec):
        rec['attached'].append(key)
        return rec
    return attach_to


class JobDB:
    def __init__(self, path):
        self.db = TinyDB(path)
        self.lock = Lock()

    def get_result_or_attach(self, key, prov, running):
        job = Query()
        with self.lock:
            rec = self.db.get(job.prov == prov)

            if 'result' in rec:
                return 'retrieved', uuid.UUID(rec['key']), rec['result']

            elif uuid.UUID(rec['key']) in running:
                self.db.update(attach_job(key.hex), job.prov == prov)
                return 'attached', uuid.UUID(rec['key']), None

            else:
                print("WARNING: unfinished job in database. Removing it and rerunning.", file=sys.stderr)
                self.db.remove(eids=[rec.eid])
                return 'broken', None, None

    def job_exists(self, prov):
        job = Query()
        with self.lock:
            return self.db.contains(job.prov == prov)

    def store_result(self, key, result):
        job = Query()
        with self.lock:
            if not self.db.contains(job.key == key.hex):
                return

        self.add_time_stamp(key, 'done')
        with self.lock:
            self.db.update({'result': result}, job.key == key.hex)
            rec = self.db.get(job.key == key.hex)
            return map(uuid.UUID, rec['attached'])

    def new_job(self, key, prov, job_msg):
        with self.lock:
            self.db.insert({
                'key': key.hex,
                'attached': [],
                'prov': prov,
                'time': {'schedule': time_stamp()},
                'version': job_msg['data']['hints'].get('version'),
                'function': job_msg['data']['function'],
                'arguments': job_msg['data']['arguments']
            })

        return key, prov

    def add_time_stamp(self, key, name):
        def update(r):
            r['time'][name] = time_stamp()

        job = Query()
        with self.lock:
            self.db.update(
                update,
                job.key == key.hex)

