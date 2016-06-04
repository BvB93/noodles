from tinydb import (TinyDB, Query)
import hashlib
import json
from threading import Lock
from ..utility import on


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
    return strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time()))
   

class JobDB:
    def __init__(self, path):
        self.db = TinyDB(path)
        self.lock = Lock()

    def get_result(self, key, prov):
        job = Query()
        with self.lock:
            rec = self.db.get(job.prov == prov)
            if rec:
                return key, rec['result']
            else:
                return None

    def set_result(self, key, result):
        job = Query()
        with self.lock:
            self.db.update({'result': result}, job.key == key)

    def new_job(self, key, job_msg):
        with self.lock:
            prov = prov_key(job_msg)
            self.db.insert({
                'key': key,
                'prov': prov,
                'time': {'schedule': time_stamp()},
                'version': job_msg['data']['hints'].get('version')
                'function': job_msg['data']['function'],
                'arguments': job_msg['data']['arguments']
            })

        return prov

    def add_time_stamp(self, key, name):
        job = Query()
        with self.lock:
            self.db.update(
                lambda r: r['time'][name] = time_stamp(),
                job.key == key)

