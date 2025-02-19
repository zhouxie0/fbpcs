#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import logging
from typing import List, Optional

from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
)
from fbpcs.service.workflow import WorkflowService, WorkflowStatus

PIDWorkflowConfigs = "PIDWorkflowConfigs"
PIDRunConfigs = "PIDRunConfigs"
PIDMR = "pid_mr"
INTPUT = "inputPath"
OUTPUT = "outputPath"
INSTANCE = "instanceId"


class PIDMRStageService(PrivateComputationStageService):
    """Handles business logic for the PID Mapreduce match stage."""

    def __init__(self, workflow_svc: WorkflowService) -> None:
        self.workflow_svc = workflow_svc
        self._logger: logging.Logger = logging.getLogger(__name__)

    async def run_async(
        self,
        pc_instance: PrivateComputationInstance,
        server_ips: Optional[List[str]] = None,
    ) -> PrivateComputationInstance:
        """This function run mr workflow service

        Args:
            pc_instance: the private computation instance to run mr match
            server_ips: only used by the partner role. These are the ip addresses of the publisher's containers.

        Returns:
            An updated version of pc_instance
        """
        self._logger.info(f"[{self}] Starting PID MR Stage Service")
        stage_state = StageStateInstance(
            pc_instance.instance_id,
            pc_instance.current_stage.name,
        )
        pid_configs = pc_instance.pid_configs
        if (
            pid_configs
            and PIDMR in pid_configs
            and PIDRunConfigs in pid_configs[PIDMR]
            and PIDWorkflowConfigs in pid_configs[PIDMR]
        ):
            pid_configs[INTPUT] = pc_instance.input_path
            pid_configs[OUTPUT] = pc_instance.pid_mr_stage_output_data_path
            pid_configs[INSTANCE] = pc_instance.instance_id
            stage_state.instance_id = self.workflow_svc.start_workflow(
                pid_configs[PIDMR][PIDWorkflowConfigs],
                pc_instance.instance_id,
                pid_configs[PIDMR][PIDRunConfigs],
            )
        pc_instance.instances.append(stage_state)
        return pc_instance

    def get_status(
        self,
        pc_instance: PrivateComputationInstance,
    ) -> PrivateComputationInstanceStatus:
        """Gets latest PrivateComputationInstance status

        Arguments:
            private_computation_instance: The PC instance that is being updated

        Returns:
            The latest status for private_computation_instance
        """
        status = pc_instance.status
        if pc_instance.instances:
            # TODO: we should have some identifier or stage_name
            # to pick up the right instance instead of the last one
            last_instance = pc_instance.instances[-1]
            if not isinstance(last_instance, StageStateInstance):
                raise ValueError(
                    f"The last instance type not StageStateInstance but {type(last_instance)}"
                )
            stage_name = last_instance.stage_name
            stage_id = last_instance.instance_id
            assert stage_name == pc_instance.current_stage.name
            pid_configs = pc_instance.pid_configs
            stage_state_instance_status = WorkflowStatus.STARTED
            if pid_configs:
                stage_state_instance_status = self.workflow_svc.get_workflow_status(
                    pid_configs[PIDMR][PIDWorkflowConfigs], stage_id
                )
            current_stage = pc_instance.current_stage
            if stage_state_instance_status in [
                WorkflowStatus.STARTED,
                WorkflowStatus.CREATED,
                WorkflowStatus.UNKNOWN,
            ]:
                status = current_stage.started_status
            elif stage_state_instance_status is WorkflowStatus.COMPLETED:
                status = current_stage.completed_status
            elif stage_state_instance_status is WorkflowStatus.FAILED:
                status = current_stage.failed_status
            else:
                raise ValueError("Unknow stage status")

        return status
