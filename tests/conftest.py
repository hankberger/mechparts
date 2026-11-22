import pytest

from mechparts.config import Settings
from mechparts.service import PartService


@pytest.fixture(scope="session")
def service(tmp_path_factory) -> PartService:
    root = tmp_path_factory.mktemp("mechparts")
    return PartService(Settings(data_dir=root, base_url="http://test", workers=0))


@pytest.fixture
def fresh_service(tmp_path) -> PartService:
    return PartService(Settings(data_dir=tmp_path, base_url="http://test", workers=0))
