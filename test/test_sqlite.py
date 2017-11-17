# import pytest

from noodles.prov.sqlite import JobDB
from noodles.prov.key import prov_key
from noodles import serial
from noodles.tutorial import (sub, add)
from noodles.run.job_keeper import JobKeeper
from noodles.run.scheduler import Job


def test_add_job():
    registry = serial.base()
    db = JobDB(':memory:', registry=serial.base())

    wf = sub(1, 1)
    job = Job(wf._workflow, wf._workflow.root)
    print('registering', job.name)
    key, node = db.register(job)
    print('key:', key)
    msg, db_id, value = db.add_job_to_db(key, node)
    print(msg, db_id)
    assert msg == 'initialized'
    
    duplicates = db.store_result_in_db(key, '0')
    assert duplicates == []

    key, node = db.register(job)
    msg, db_id, value = db.add_job_to_db(key, node)
    assert msg == 'retrieved'
    assert value == '0'


def test_attaching():
    registry = serial.base()
    db = JobDB(':memory:', registry=serial.base())

    wf = add(1, 1)
    job = Job(wf._workflow, wf._workflow.root)
    key1, node1 = db.register(job)
    msg, db_id, value = db.add_job_to_db(key1, node1)
    assert msg == 'initialized'

    key2, node2 = db.register(job)
    msg, db_id, value = db.add_job_to_db(key2, node2)
    assert msg == 'attached'
    assert db_id == key1

    duplicates = db.store_result_in_db(key1, '2')
    assert duplicates == [key2]

    key3, node3 = db.register(job)
    msg, db_id, value = db.add_job_to_db(key3, node3)
    assert msg == 'retrieved'
    assert value == '2'


