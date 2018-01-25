from noodles import run_single
from noodles import run_parallel
from noodles import run_process, serial
from noodles.serial.numpy import arrays_to_string
from .backend_factory import backend_factory


def registry():
    return serial.pickle() + serial.base() + arrays_to_string()


backends = {
    'single': backend_factory(
        run_single, supports=['local']),
    'threads-4': backend_factory(
        run_parallel, supports=['local'], n_threads=4),
    'processes-2': backend_factory(
        run_process, supports=['remote'], n_processes=2, registry=registry,
        verbose=True),
    'processes-2-msgpack': backend_factory(
        run_process, supports=['remote'], n_processes=2, registry=registry,
        use_msgpack=True)
}

__all__ = ['backends']