from ctypes import (
    Structure,
    byref,
    c_uint64,
    c_int,
    POINTER,
    CDLL,
)
from pkg_resources import resource_filename
import os
from subprocess import call


class Counter(Structure):
    _fields_ = [
        ("time_enabled_ns", c_uint64),
        ("instruction_count", c_uint64),
        ("branch_misses", c_uint64),
        ("page_faults", c_uint64),
    ]

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        repr = "Counter("

        for field, _ in Counter._fields_:
            repr += f"{field}={getattr(self, field)}, "
        repr = repr[:-2] + ")"

        return repr


lib_path = resource_filename(__name__, "cirronlib.so")
if not os.path.exists(lib_path):
    source_path = resource_filename(__name__, "cirronlib.c")
    exit_status = call(f"gcc -shared -fPIC -o {lib_path} {source_path}", shell=True)
    if exit_status != 0:
        raise Exception(
            "Failed to compile cirronlib.c, make sure you have gcc installed."
        )

cirron_lib = CDLL(lib_path)
cirron_lib.start.argtypes = None
cirron_lib.start.restype = c_int
cirron_lib.end.argtypes = [c_int, POINTER(Counter)]
cirron_lib.end.restype = None


class Collector:
    def __init__(self):
        self.fd = None
        self.counter = Counter()

    def start(self):
        ret_val = cirron_lib.start()
        if ret_val == -1:
            raise Exception("Failed to start collector.")
        self.fd = ret_val

    def end(self):
        ret_val = cirron_lib.end(self.fd, byref(self.counter))
        if ret_val == -1:
            raise Exception("Failed to end collector.")

        global overhead
        if overhead:
            for field, _ in Counter._fields_:
                setattr(
                    self.counter, field, getattr(self.counter, field) - overhead[field]
                )
        return self.counter


# We try to estimate what the overhead of the collector is, taking the minimum
# of 10 runs.
overhead = {}
collector = Collector()
o = {}
for _ in range(10):
    collector.start()
    collector.end()

    for field, _ in Counter._fields_:
        if field not in overhead:
            o[field] = getattr(collector.counter, field)
        else:
            o[field] = min(overhead[field], getattr(collector.counter, field))
overhead = o
del collector
