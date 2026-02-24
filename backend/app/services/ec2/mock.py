import time
import uuid
import random

from app.services.ec2.base import EC2Backend

TIER_INSTANCE_MAP = {
    "small":  "t3.small",
    "medium": "t3.medium",
    "large":  "c5.2xlarge",
}


class MockEC2Backend(EC2Backend):
    def spawn_instance(self, tier: str) -> str:
        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)
        instance_id = f"i-mock-{uuid.uuid4().hex[:8]}"
        return instance_id

    def terminate_instance(self, instance_id: str) -> None:
        time.sleep(0.5)
