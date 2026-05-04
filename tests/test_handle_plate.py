"""Unit tests for plate search handlers."""

import pytest

from buscamaes.sources.rnp import VehicleResult


class TestDoPlateSearch:
    """Test plate search handler logic."""

    @pytest.mark.asyncio
    async def test_vehicle_result_with_no_marca_returns_not_found(self):
        """Test that empty marca field is treated as not found."""

        vehicle = VehicleResult()

        # Verify the logic: if not vehicle.marca returns True for empty result
        assert not vehicle.marca

    def test_escape_markdown_integration(self):
        """Test that vehicle formatter escapes Markdown."""
        from buscamaes.bot.formatting import _format_vehicle

        vehicle = VehicleResult(
            placa="ABC 123",
            marca="BMW (M-SERIES)",
            categoria="Auto",
            estilo="SEDAN",
        )
        result = _format_vehicle(vehicle)

        # Verify parens are escaped
        assert r"\(" in result
        assert r"\)" in result
