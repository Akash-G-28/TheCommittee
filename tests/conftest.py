from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from the_committee.agents import deterministic_agents
from the_committee.api import create_app
from the_committee.chairperson import Chairperson
from the_committee.orchestration import CommitteeService
from the_committee.persistence import Base, SqlAlchemyDecisionRepository, create_database


@pytest.fixture
def service(tmp_path: Path) -> CommitteeService:
    engine, sessions = create_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return CommitteeService(
        SqlAlchemyDecisionRepository(sessions), deterministic_agents(), Chairperson()
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(f"sqlite:///{tmp_path / 'api.db'}")
    with TestClient(app) as test_client:
        yield test_client

