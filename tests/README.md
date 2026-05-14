# PatchRaptor Testing Guide

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific test file:
```bash
pytest tests/test_rcon_manager.py
```

### Run specific test:
```bash
pytest tests/test_rcon_manager.py::TestRCONCommandValidation::test_safe_commands_allowed
```

### Run with coverage:
```bash
pytest --cov=patchraptor --cov-report=html
```

### Run only fast tests (skip slow/integration):
```bash
pytest -m "not slow"
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_rcon_manager.py     # RCON validation tests
├── test_config.py           # Config loading tests
└── test_player_manager.py   # Player management tests
```

## Writing New Tests

### 1. Create a new test file:
```python
# tests/test_my_feature.py
import pytest

class TestMyFeature:
    def test_something(self):
        assert True
```

### 2. Use fixtures from conftest.py:
```python
def test_with_config(mock_config_data):
    assert mock_config_data["discord_token"] == "test_token_123"
```

### 3. Test async code:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## Test Categories

- **Unit tests**: Fast, no external dependencies
- **Integration tests**: May require RCON/Discord connections
- **Slow tests**: Take several seconds to run

Mark tests appropriately:
```python
@pytest.mark.slow
def test_long_running_operation():
    # ...
```

## Current Test Coverage

- ✅ RCON command validation
- ✅ Config loading and validation
- ✅ Player ban management
- ✅ Pause/resume functionality
- ✅ Server management (Verified)
- ✅ Update management (Verified)
- ✅ Discord commands (Verified)
