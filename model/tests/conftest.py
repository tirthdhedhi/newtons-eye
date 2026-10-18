import pytest

from parser_model.solve import solver_available


def pytest_collection_modifyitems(config, items):
    if solver_available():
        return
    skip = pytest.mark.skip(reason="pnpm solver unavailable (needs pnpm and Node 24)")
    for item in items:
        if "solver" in item.keywords:
            item.add_marker(skip)
