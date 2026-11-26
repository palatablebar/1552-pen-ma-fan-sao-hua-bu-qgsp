"""Named planning alias for the minimum supplemental-frame certificate."""

from .reshoot import *  # noqa: F401,F403
from .reshoot import (  # noqa: F401
    FRAME_LIMIT,
    ReshootDecision,
    certify_minimum_reshoot,
    certify_reshoot,
    minimum_reshoot_count,
    plan_minimum_reshoot,
)

build_plan = certify_reshoot
minimum_supplemental_frames = certify_minimum_reshoot
reshoot_plan = certify_reshoot
sign_minimum_reshoot = certify_reshoot

__all__ = (
    'FRAME_LIMIT',
    'ReshootDecision',
    'certify_reshoot',
    'certify_minimum_reshoot',
    'minimum_reshoot_count',
    'plan_minimum_reshoot',
    'build_plan',
    'minimum_supplemental_frames',
    'reshoot_plan',
    'sign_minimum_reshoot',
)
