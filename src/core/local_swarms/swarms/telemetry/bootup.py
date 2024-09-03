import os
import logging
import warnings

from src.core.local_swarms.swarms.telemetry.auto_upgrade_swarms import auto_update
from src.core.local_swarms.swarms.utils.disable_logging import disable_logging


def bootup():
    """Bootup swarms"""
    disable_logging()
    logging.disable(logging.CRITICAL)
    os.environ["WANDB_SILENT"] = "true"
    os.environ["WORKSPACE_DIR"] = "agent_workspace"
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    auto_update()