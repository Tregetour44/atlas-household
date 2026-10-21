"""Run the ESPHome CLI with the build timestamp taken from SOURCE_DATE_EPOCH.

ESPHome 2026.9.1 stamps time.time() into every image (ESPHOME_BUILD_TIME and
its string form, see esphome/writer.py get_build_info). That is the only
clock input; ESP-IDF's CONFIG_APP_REPRODUCIBLE_BUILD is already on. Fixing
it makes two clean builds byte-identical. On the device the value is only
reported as the compilation time and used as a lower bound for the clock.

Usage: SOURCE_DATE_EPOCH=<seconds> python -I esphome_repro.py compile <config.yaml>
"""

import os
import sys
import time

import esphome.writer
from esphome.core import CORE

EPOCH = int(os.environ["SOURCE_DATE_EPOCH"])


def get_build_info() -> tuple[int, int, str, str]:
    build_time_str = time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime(EPOCH))
    return CORE.config_hash, EPOCH, build_time_str, CORE.comment or ""


esphome.writer.get_build_info = get_build_info

from esphome.__main__ import main  # noqa: E402

sys.exit(main())
