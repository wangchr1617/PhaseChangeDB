from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.observation import ObservationCreate


def test_observation_requires_exactly_one_subject() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        ObservationCreate(property_definition_id=uuid4(), value_numeric=453)


def test_measurement_requires_sample_subject() -> None:
    with pytest.raises(ValidationError, match="measurement_id requires sample_id"):
        ObservationCreate(
            device_id=uuid4(),
            measurement_id=uuid4(),
            property_definition_id=uuid4(),
            value_numeric=453,
        )


def test_range_rejects_reversed_bounds() -> None:
    with pytest.raises(ValidationError, match="value_min must not exceed value_max"):
        ObservationCreate(
            sample_id=uuid4(),
            property_definition_id=uuid4(),
            value_kind="range",
            value_min=500,
            value_max=400,
        )
