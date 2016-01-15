from .coroutines import coroutine_sink, Connection
from .data_json import json_sauce, desaucer, node_to_jobject
from .logger import log
# from .run_common import Schedule
import json
import uuid
import xenon
import os
import sys
import time
from queue import Queue
import threading

xenon.init(log_level='ERROR')  # noqa

from jnius import autoclass


def read_result(s):
    obj = json.loads(s, object_hook=desaucer())
    return (uuid.UUID(obj['key']), obj['result'])


def put_job(key, job):
    obj = {'key': key.hex,
           'node': node_to_jobject(job.node())}
    return json.dumps(obj, default=json_sauce)


jPrintStream = autoclass('java.io.PrintStream')
jBufferedReader = autoclass('java.io.BufferedReader')
jInputStreamReader = autoclass('java.io.InputStreamReader')
jScanner = autoclass('java.util.Scanner')


def jLines(inp):
    reader = jScanner(inp)

    while True:
        line = reader.nextLine()
        yield line


class XenonJob:
    def __init__(self, keeper, job, desc):
        self.keeper = keeper
        self.job = job
        self.desc = desc

        if self.interactive:
            self.streams = self.get_streams()

    def wait_until_running(self, timeout):
        status = self.keeper.jobs.waitUntilRunning(
            self.job, timeout)
        return status

    def get_streams(self):
        return self.keeper.jobs.getStreams(self.job)

    @property
    def interactive(self):
        return self.job.isInteractive()


class XenonKeeper:
    def __init__(self,
                 scheduler_args=('local', None, None, None)):
        self.x = xenon.Xenon()
        self.jobs = self.x.jobs()
        self.scheduler = self.jobs.newScheduler(*scheduler_args)

    def submit(self, command, interactive=True):
        desc = xenon.jobs.JobDescription()
        if interactive:
            desc.setInteractive(True)
        desc.setExecutable(command[0])
        desc.setArguments(*command[1:])
        job = self.jobs.submitJob(self.scheduler, desc)
        return XenonJob(self, job, desc)


class XenonConfig:
    def __init__(self):
        self.jobs_scheme = 'local'
        self.files_scheme = 'local'
        self.location = None
        self.credentials = None
        self.jobs_properties = None
        self.files_properties = None
        self.working_dir = os.getcwd()
        self.exec_command = None
        self.time_out = 5000  # 5 seconds
        self.prefix = sys.prefix

    @property
    def scheduler_args(self):
        return (self.jobs_scheme, self.location,
                self.credentials, self.jobs_properties)

    @property
    def filesystem_args(self):
        return (self.files_scheme, self.location,
                self.credentials, self.files_properties)


def xenon_interactive_worker(config=None):
    """Uses Xenon to run a single remote interactive worker.

    Jobs are read from stdin, and results written to stdout.
    """

    if config is None:
        config = XenonConfig()  # default config

    K = XenonKeeper(config.scheduler_args)

    if config.exec_command is None:
        config.exec_command = [
            '/bin/bash',
            config.working_dir + '/worker.sh',
            config.prefix,
            'online']

    J = K.submit(config.exec_command, interactive=True)

    status = J.wait_until_running(config.time_out)
    if not status.isRunning():
        raise RuntimeError("Could not get the job running")

    def read_stderr():
        for line in jLines(J.streams.getStderr()):
            log.worker_stderr("Xe {0:X}".format(id(K)), line)

    K.stderr_thread = threading.Thread(target=read_stderr)
    K.stderr_thread.daemon = True
    K.stderr_thread.start()

    @coroutine_sink
    def send_job():
        out = jPrintStream(J.streams.getStdin())

        while True:
            key, ujob = yield
            out.println(put_job(key, ujob))
            out.flush()

    def get_result():
        for line in jLines(J.streams.getStdout()):
            key, result = read_result(line)
            yield (key, result)

    return Connection(get_result, send_job)


def xenon_batch_worker(poll_delay=1):
    xenon.init()

    x = xenon.Xenon()
    jobs_api = x.jobs()

    new_jobs = Queue()

    @coroutine_sink
    def send_job():
        sched = jobs_api.newScheduler('ssh', 'localhost', None, None)

        while True:
            key, job = yield
            pwd = 'noodles-{0}'.format(key.hex)
            desc = xenon.jobs.JobDescription()
            desc.setExecutable('python3.5')
            desc.setStdout(os.getcwd() + '/' + pwd + '/out.json')

            # submit a job
            job = jobs_api.submitJob(sched, desc)
            new_jobs.put((key, job))

    def get_result():
        jobs = {}

        while True:
            time.sleep(poll_delay)
            for key, job in jobs.items():
                ...
                result = 42
                yield (key, result)

            # put recently submitted jobs into the jobs-dict.
            while not new_jobs.empty():
                key, job = new_jobs.get()
                jobs[key] = job
                new_jobs.task_done()

    return Connection(get_result, send_job)
