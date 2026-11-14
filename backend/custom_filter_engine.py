
import math
from typing import Literal, Mapping

from pydantic import BaseModel, Field, model_validator


MetricName = Literal[
    "sunlightPercent",
    "earthVisibilityPercent",
    "maxDarknessHours",
    "maxCommunicationBlackoutHours",
]


class CustomFilterRule(BaseModel):
    id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )

    label: str = Field(min_length=1, max_length=100)

    metric: MetricName

    operator: Literal["gte", "lte"]

    threshold: float = Field(ge=0, le=8760)

    enabled: bool = True

    @model_validator(mode="after")
    def validate_threshold(self):
        percentage_metrics = {
            "sunlightPercent",
            "earthVisibilityPercent",
        }

        if (
            self.metric in percentage_metrics
            and self.threshold > 100
        ):
            raise ValueError(
                "Percentage thresholds cannot exceed 100."
            )

        return self


def evaluate_custom_filters(
    rules: list[CustomFilterRule],
    scientific_metrics: Mapping[str, float],
) -> list[dict]:
    """
    Evaluate uploaded rules against real engine results.

    This function does not calculate lunar ephemerides.
    It evaluates requirements after scientific calculations.
    """

    evaluations = []

    for rule in rules:
        if not rule.enabled:
            continue

        actual = scientific_metrics.get(rule.metric)

        if (
            actual is None
            or not isinstance(actual, (int, float))
            or not math.isfinite(actual)
        ):
            evaluations.append({
                "id": rule.id,
                "actualValue": None,
                "passed": None,
                "message": "Metric not available from engine",
            })
            continue

        if rule.operator == "gte":
            passed = actual >= rule.threshold
        else:
            passed = actual <= rule.threshold

        evaluations.append({
            "id": rule.id,
            "actualValue": float(actual),
            "passed": passed,
            "message": (
                "Requirement satisfied"
                if passed
                else "Requirement not satisfied"
            ),
        })

    return evaluations
