from parsl.addresses import address_by_query
from parsl.launchers import SrunLauncher
from parsl.providers import SlurmProvider

from funcx_endpoint.endpoint.utils.config import Config
from funcx_endpoint.executors import HighThroughputExecutor

user_opts = {
    'delta': {
        'worker_init': 'bash',
        'scheduler_options': '#SBATCH --account=bbmi-delta-cpu',
    }
}

config = Config(
    executors=[
        HighThroughputExecutor(
            max_workers_per_node=2,
            mem_per_worker=500,
            worker_debug=True,
            address=address_by_query(),
            provider=SlurmProvider(
                partition='cpu',
                launcher=SrunLauncher(),
                # string to prepend to #SBATCH blocks in the submit
                # script to the scheduler eg: '#SBATCH --constraint=knl,quad,cache'
                scheduler_options=user_opts['delta']['scheduler_options'],

                # Command to be run before starting a worker, such as:
                # 'module load Anaconda; source activate parsl_env'.
                worker_init=user_opts['delta']['worker_init'],

                # Scale between 0-1 blocks with 2 nodes per block
                nodes_per_block=2,
                init_blocks=0,
                min_blocks=0,
                mem_per_node=10,
                max_blocks=10,

                # Hold blocks for 30 minutes
                walltime='06:00:00'
            ),
        )
    ],
    heartbeat_period=15,
    heartbeat_threshold=300
)
