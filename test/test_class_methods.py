from noodles import schedule, has_scheduled_methods, run, Scheduler, Storable
from noodles.run_process import process_worker
from noodles.datamodel import get_workflow


@has_scheduled_methods
class A(Storable):
    def __init__(self, x):
        super(A, self).__init__()
        self.x = x

    @schedule
    def __call__(self, y):
        return self.x * y


def test_class_methods_00():
    a = A(7)
    b = a(6)

    result = run(b)
    assert result == 42


def test_class_methods_01():
    a = A(7)
    b = a(6)

    result = Scheduler().run(process_worker(), get_workflow(b))
    assert result == 42
