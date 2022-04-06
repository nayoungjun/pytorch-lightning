# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os

import pytest
import torch
import torch.multiprocessing as mp

import tests.helpers.utils as tutils
from pytorch_lightning.utilities.distributed import _collect_states_on_rank_zero, gather_all_tensors
from tests.helpers.runif import RunIf


def _test_collect_states(rank, world_size):
    os.environ["MASTER_ADDR"] = "localhost"

    torch.cuda.set_device(f"cuda:{rank}")

    # initialize the process group
    torch.distributed.init_process_group("nccl", rank=rank, world_size=world_size)

    state = {"something": torch.tensor([rank])}
    collected_state = _collect_states_on_rank_zero(state)
    assert collected_state == {1: {"something": torch.tensor([1])}, 0: {"something": torch.tensor([0])}}


@RunIf(min_gpus=2, min_torch="1.10", skip_windows=True)
def test_collect_states():
    """This test ensures state are properly collected across processes.

    This would be used to collect dataloader states as an example.
    """
    tutils.set_random_main_port()
    mp.spawn(_test_collect_states, args=(2,), nprocs=2)


def _test_all_gather_uneven_tensors(rank, world_size):
    os.environ["MASTER_ADDR"] = "localhost"

    torch.cuda.set_device(f"cuda:{rank}")

    # initialize the process group
    torch.distributed.init_process_group("nccl", rank=rank, world_size=world_size)

    tensor = torch.ones(rank)
    result = gather_all_tensors(tensor)
    assert len(result) == world_size
    for idx in range(world_size):
        assert len(result[idx]) == idx
        assert (result[idx] == torch.ones_like(result[idx])).all()


def _test_all_gather_uneven_tensors_multidim(rank, world_size):
    os.environ["MASTER_ADDR"] = "localhost"

    torch.cuda.set_device(f"cuda:{rank}")

    # initialize the process group
    torch.distributed.init_process_group("nccl", rank=rank, world_size=world_size)
    tensor = torch.ones(rank + 1, 2 - rank)
    result = gather_all_tensors(tensor)
    assert len(result) == world_size
    for idx in range(world_size):
        val = result[idx]
        assert val.shape == (idx + 1, 2 - idx)
        assert (val == torch.ones_like(val)).all()


@RunIf(min_gpus=2, min_torch="1.10", skip_windows=True)
@pytest.mark.parametrize(
    "process",
    [
        _test_all_gather_uneven_tensors_multidim,
        _test_all_gather_uneven_tensors,
    ],
)
def test_gather_all_tensors(process):
    tutils.set_random_main_port()
    mp.spawn(process, args=(2,), nprocs=2)
