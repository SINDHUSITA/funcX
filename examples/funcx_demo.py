
from funcx import FuncXExecutor

def print_hw():
    return "Hello world"


with FuncXExecutor(endpoint_id="b41a2cf6-ee51-4060-8317-27e2ac8e4891") as ex:
    fut = ex.submit(print_hw)

    print(fut.result())


