"""Run piper1-gpl's LightningCLI without its default val_mel/val_mos checkpoint callbacks, so only the callbacks in
configs/piper_train.yaml are used (step checkpoints every 500 steps + last.ckpt). Note: Lightning's global step
advances twice per batch here (generator + discriminator optimisers), so 500 steps = 250 batches."""
import logging
from piper.train.__main__ import VitsLightningCLI
from piper.train.vits.dataset import VitsDataModule
from piper.train.vits.lightning import VitsModel

logging.basicConfig(level=logging.INFO)
VitsLightningCLI(VitsModel, VitsDataModule, trainer_defaults={"max_epochs": -1})
