
from funcx import FuncXExecutor

def print_hw():
    return "Hello world"


with FuncXExecutor(endpoint_id="915d4ae6-52f1-4cbf-b841-3e19db3fd121") as ex:
    fut = ex.submit(print_hw)

    print(fut.result())


