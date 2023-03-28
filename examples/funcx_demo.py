
from funcx import FuncXExecutor

def print_hw():
    import numpy as np 
    return "Hello world"


with FuncXExecutor(endpoint_id="d26f1116-219f-463f-9697-233506ec66c0") as ex:
    fut = ex.submit(print_hw)

    print(fut.result())


