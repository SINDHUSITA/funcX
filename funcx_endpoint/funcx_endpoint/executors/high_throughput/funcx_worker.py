from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

import dill
import zmq
from funcx_common import messagepack
from funcx_common.messagepack.message_types import TaskTransition
from funcx_common.tasks import ActorName, TaskState

from funcx.errors import MaxResultSizeExceeded
from funcx.serialize import FuncXSerializer
from funcx_endpoint.exception_handling import get_error_string, get_result_error_details
from funcx_endpoint.exceptions import CouldNotExecuteUserTaskError
from funcx_endpoint.executors.high_throughput.messages import Message
from funcx_endpoint.logging_config import setup_logging

log = logging.getLogger(__name__)

DEFAULT_RESULT_SIZE_LIMIT_MB = 10
DEFAULT_RESULT_SIZE_LIMIT_B = DEFAULT_RESULT_SIZE_LIMIT_MB * 1024 * 1024


class FuncXWorker:
    """The FuncX worker
    Parameters
    ----------

    worker_id : str
     Worker id string

    address : str
     Address at which the manager might be reached. This is usually 127.0.0.1

    port : int
     Port at which the manager can be reached

    result_size_limit : int
     Maximum result size allowed in Bytes
     Default = 10 MB

    Funcx worker will use the REP sockets to:
         task = recv ()
         result = execute(task)
         send(result)
    """

    def __init__(
        self,
        worker_id,
        address,
        port,
        worker_type="RAW",
        result_size_limit=DEFAULT_RESULT_SIZE_LIMIT_B,
    ):
        self.worker_id = worker_id
        self.address = address
        self.port = port
        self.worker_type = worker_type
        self.serializer = FuncXSerializer()
        self.serialize = self.serializer.serialize
        self.deserialize = self.serializer.deserialize
        self.result_size_limit = result_size_limit

        log.info(f"Initializing worker {worker_id}")
        log.info(f"Worker is of type: {worker_type}")

        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.identity = worker_id.encode()

        self.task_socket = self.context.socket(zmq.DEALER)
        self.task_socket.setsockopt(zmq.IDENTITY, self.identity)

        log.info(f"Trying to connect to : tcp://{self.address}:{self.port}")
        self.task_socket.connect(f"tcp://{self.address}:{self.port}")
        self.poller.register(self.task_socket, zmq.POLLIN)
        signal.signal(signal.SIGTERM, self.handler)

    def handler(self, signum, frame):
        log.error(f"Signal handler called with signal {signum}")
        sys.exit(1)

    def _send_registration_message(self):
        #TODO revert
        log.info("Sending registration")
        payload = {"worker_id": self.worker_id, "worker_type": self.worker_type}
        self.task_socket.send_multipart([b"REGISTER", dill.dumps(payload)])

    def start(self):
        log.info("Starting worker")
        self._send_registration_message()

        #TODO Revert
        log.info("VSI3  Entering while loop")

        while True:
            #TODO Revert
            log.info("Waiting for task")
            p_task_id, p_container_id, msg = self.task_socket.recv_multipart()
            log.info(f"VSI3 p_tasks_id {p_task_id}")
            task_id: str = dill.loads(p_task_id)
            container_id: str = dill.loads(p_container_id)
            #TODO Revert
            log.info(f"Received task with task_id='{task_id}' and msg='{msg}'")

            result = None
            if task_id == "KILL":
                log.info("[KILL] -- Worker KILL message received! ")
                # send a "worker die" message back to the manager
                self.task_socket.send_multipart([b"WRKR_DIE", b""])
                log.info(f"*** WORKER {self.worker_id} ABOUT TO DIE ***")
                # Kill the worker after accepting death in message to manager.
                sys.exit()
            else:
                result = self.execute_task(task_id, msg)
                log.info("BENC: 00120 returned from execute task")
                result["container_id"] = container_id
                # TODO Revert
                log.info("Sending result")
                # send bytes over the socket back to the manager
                self.task_socket.send_multipart([b"TASK_RET", dill.dumps(result)])
                log.info("BENC: 00121 send result over task_socket")

        #TODO Revert
        log.info("Broke out of the loop... dying")

    def execute_task(self, task_id: str, task_body: bytes) -> dict:
        # TODO Revert
        log.info("executing task task_id='%s'", task_id)
        exec_start = TaskTransition(
            timestamp=time.time_ns(), state=TaskState.EXEC_START, actor=ActorName.WORKER
        )

        try:
            result = self.call_user_function(task_body)
            log.info("BENC: 00110 returned from call user function")
        except Exception:
            # TODO Revert
            log.info("Caught an exception while executing user function")
            result_message: dict[
                str, str | tuple[str, str] | list[TaskTransition]
            ] = dict(
                task_id=task_id,
                exception=get_error_string(),
                error_details=get_result_error_details(),
            )

        else:
            #TODO Revert
            log.info("Execution completed without exception")
            result_message = dict(task_id=task_id, data=result)

        exec_end = TaskTransition(
            timestamp=time.time_ns(),
            state=TaskState.EXEC_END,
            actor=ActorName.WORKER,
        )

        result_message["task_statuses"] = [exec_start, exec_end]

        # TODO Revert
        log.info(
            "task %s completed in %d ns",
            task_id,
            (exec_end.timestamp - exec_start.timestamp),
        )
        log.info("BENC: 00111 returning result_message from execute task")
        return result_message

    def call_user_function(self, message: bytes) -> str:
        """Deserialize the buffer and execute the task.

        Returns the result or throws exception.
        """
        # try to unpack it as a messagepack message
        try:
            task = messagepack.unpack(message)
            if not isinstance(task, messagepack.message_types.Task):
                raise CouldNotExecuteUserTaskError(
                    f"wrong type of message in worker: {type(task)}"
                )
            task_data = task.task_buffer
        # on parse errors, failover to trying the "legacy" message reading
        except (
            messagepack.InvalidMessageError,
            messagepack.UnrecognizedProtocolVersion,
        ):
            task = Message.unpack(message)
            task_data = task.task_buffer.decode("utf-8")  # type: ignore[attr-defined]

        f, args, kwargs = self.serializer.unpack_and_deserialize(task_data)
        result_data = f(*args, **kwargs)
        log.info("BENC: 00100 serializing data on worker")
        serialized_data = self.serialize(result_data)
        log.info("BENC: 00101 serialized data on worker")

        if len(serialized_data) > self.result_size_limit:
            raise MaxResultSizeExceeded(len(serialized_data), self.result_size_limit)

        log.info("BENC: 00102 returning serialized data")
        return serialized_data


def cli_run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w", "--worker_id", required=True, help="ID of worker from process_worker_pool"
    )
    parser.add_argument(
        "-t", "--type", required=False, help="Container type of worker", default="RAW"
    )
    parser.add_argument(
        "-a", "--address", required=True, help="Address for the manager, eg X,Y,"
    )
    parser.add_argument(
        "-p",
        "--port",
        required=True,
        help="Internal port at which the worker connects to the manager",
    )
    parser.add_argument(
        "--logdir", required=True, help="Directory path where worker log files written"
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Directory path where worker log files written",
    )
    args = parser.parse_args()

    setup_logging(
        logfile=os.path.join(args.logdir, f"funcx_worker_{args.worker_id}.log"),
        debug=args.debug,
    )

    # Redirect the stdout and stderr
    stdout_path = os.path.join(args.logdir, f"funcx_worker_{args.worker_id}.stdout")
    stderr_path = os.path.join(args.logdir, f"funcx_worker_{args.worker_id}.stderr")
    with open(stdout_path, "w") as fo, open(stderr_path, "w") as fe:
        # Redirect the stdout
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = fo
        sys.stderr = fe

        try:
            worker = FuncXWorker(
                args.worker_id,
                args.address,
                int(args.port),
                worker_type=args.type,
            )
            worker.start()
        finally:
            # Switch them back
            sys.stdout = old_stdout
            sys.stderr = old_stderr


if __name__ == "__main__":
    cli_run()

# /u/ritwikd2/.conda/envs/funcx-debug/lib/python3.9/site-packages/funcx_endpoint/executors/high_throughput