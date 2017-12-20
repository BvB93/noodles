"""
Next generation class of Workflow Runners. These are accessed by configuring
Noodles in a `noodles.ini` file. For this reason they have to obey similar
interfaces.
"""

from ..lib import (Queue, push_map, sink_map, branch, patch, thread_pool)
from ..workflow import (get_workflow)

from .worker import (worker)
from .scheduler import (Scheduler)
from .messages import (EndOfWork)

from itertools import (repeat)
import threading


# =========================================================================== #
def run_single(wf):
    """Run a workflow in a single thread. This is the absolute minimal
    runner, consisting of a single queue for jobs and a worker running
    jobs every time a result is pulled."""
    S = Scheduler()
    W = Queue() >> worker

    return S.run(W, get_workflow(wf))


def run_single_with_display(wf, display):
    """Adds a display to the single runner. Everything still runs in a single
    thread. Every time a job is pulled by the worker, a message goes to the
    display routine; when the job is finished the result is sent to the display
    routine."""

    @push_map
    def log_job_start(key, job):
        return (key, 'start', job, None)

    S = Scheduler(error_handler=display.error_handler)
    W = Queue() \
        >> branch(log_job_start.to(sink_map(display))) \
        >> worker \
        >> branch(sink_map(display))

    return S.run(W, get_workflow(wf))


def run_parallel(wf, n_threads):
    """Run a workflow in `n_threads` parallel threads. Now we replaced the
    single worker with a thread-pool of workers."""
    S = Scheduler()
    W = Queue() >> thread_pool(*repeat(worker, n_threads),
                               end_of_queue=EndOfWork)

    return S.run(W, get_workflow(wf))


def run_parallel_with_display(wf, n_threads, display):
    """Adds a display to the parallel runner. Because messages come in
    asynchronously now, we start an extra thread just for the display
    routine."""

    @push_map
    def log_job_start(key, job):
        return (key, 'start', job, None)

    LogQ = Queue(end_of_queue=EndOfWork)

    S = Scheduler(error_handler=display.error_handler)

    t = threading.Thread(
        target=patch,
        args=(LogQ.source, sink_map(display)),
        daemon=True)
    t.start()

    W = Queue() \
        >> branch(log_job_start >> LogQ.sink) \
        >> thread_pool(*repeat(worker, n_threads),
                       end_of_queue=EndOfWork) \
        >> branch(LogQ.sink)

    result = S.run(W, get_workflow(wf))
    LogQ.close()
    t.join()
    LogQ.wait()

    return result
