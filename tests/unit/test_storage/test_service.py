"""Tests for app.storage.service module.

Covers:
    - write_blob with mock backend
    - reconstruct_blob
    - delete_blob (soft and hard)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage.config import StorageConfig
from app.storage.service import StorageService


def _make_mock_timepoint(**overrides):
    tp = MagicMock()
    tp.id = overrides.get("id", "tp-test-123")
    tp.query = overrides.get("query", "Tesla hotel 1943")
    tp.slug = overrides.get("slug", "tesla-hotel-1943-abc123")
    tp.year = overrides.get("year", 1943)
    tp.month = overrides.get("month", 1)
    tp.era = overrides.get("era", "WWII")
    tp.location = overrides.get("location", "New York")
    tp.text_model_used = overrides.get("text_model_used", "gemini-2.5-flash")
    tp.image_model_used = overrides.get("image_model_used", None)
    tp.created_at = overrides.get("created_at", datetime(2026, 2, 9, tzinfo=timezone.utc))
    tp.parent_id = overrides.get("parent_id", None)
    tp.error_message = None
    tp.status = MagicMock()
    tp.status.value = "completed"

    # JSON data
    tp.metadata_json = overrides.get("metadata_json", {"timeline": {"year": 1943}})
    tp.scene_data_json = overrides.get("scene_data_json", {"setting": "hotel lobby"})
    tp.character_data_json = overrides.get("character_data_json", {"characters": []})
    tp.dialog_json = overrides.get("dialog_json", [{"speaker": "Tesla", "line": "Hello"}])
    tp.grounding_data_json = overrides.get("grounding_data_json", None)
    tp.moment_data_json = overrides.get("moment_data_json", None)
    tp.image_prompt = overrides.get("image_prompt", "A photorealistic image of Tesla")
    tp.image_base64 = overrides.get("image_base64", None)

    # Blob fields
    tp.blob_path = overrides.get("blob_path", None)
    tp.blob_folder_name = overrides.get("blob_folder_name", None)

    # New fields
    tp.sequence_id = overrides.get("sequence_id", None)
    tp.nsfw_flag = overrides.get("nsfw_flag", False)
    tp.render_type = overrides.get("render_type", "image")
    tp.created_by = overrides.get("created_by", None)
    tp.api_source = overrides.get("api_source", None)
    tp.view_count = overrides.get("view_count", 0)
    tp.last_accessed_at = overrides.get("last_accessed_at", None)
    tp.generation_version = overrides.get("generation_version", 1)
    tp.tags_json = overrides.get("tags_json", None)

    return tp


def _make_mock_backend():
    backend = AsyncMock()
    backend.write_file = AsyncMock()
    backend.write_text = AsyncMock()
    backend.delete_directory = AsyncMock()
    backend.move_directory = AsyncMock()
    backend.exists = AsyncMock(return_value=False)
    return backend


@pytest.fixture
def config():
    return StorageConfig(enabled=True, root="/tmp/test_blobs")


@pytest.fixture
def mock_backend():
    return _make_mock_backend()


@pytest.fixture
def service(config, mock_backend):
    return StorageService(config=config, backend=mock_backend)


class TestWriteBlob:
    """Tests for StorageService.write_blob()."""

    @pytest.mark.asyncio
    async def test_returns_path_and_name(self, service):
        tp = _make_mock_timepoint()
        path, name = await service.write_blob(tp)
        assert path.startswith("/tmp/test_blobs/")
        assert name  # non-empty

    @pytest.mark.asyncio
    async def test_writes_json_sidecars(self, service, mock_backend):
        tp = _make_mock_timepoint()
        await service.write_blob(tp)
        # Should write metadata.json, scene.json, characters.json, dialog.json
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "metadata.json" in filenames
        assert "scene.json" in filenames
        assert "characters.json" in filenames
        assert "dialog.json" in filenames

    @pytest.mark.asyncio
    async def test_writes_image_prompt(self, service, mock_backend):
        tp = _make_mock_timepoint(image_prompt="A test prompt")
        await service.write_blob(tp)
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "image_prompt.txt" in filenames

    @pytest.mark.asyncio
    async def test_writes_provenance(self, service, mock_backend):
        tp = _make_mock_timepoint()
        await service.write_blob(tp)
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "provenance.json" in filenames

    @pytest.mark.asyncio
    async def test_writes_manifest(self, service, mock_backend):
        tp = _make_mock_timepoint()
        await service.write_blob(tp)
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "manifest.json" in filenames

    @pytest.mark.asyncio
    async def test_writes_index_html(self, service, mock_backend):
        tp = _make_mock_timepoint()
        await service.write_blob(tp)
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "index.html" in filenames

    @pytest.mark.asyncio
    async def test_writes_image_when_base64_present(self, service, mock_backend):
        # PNG base64 starts with iVBOR
        tp = _make_mock_timepoint(image_base64="iVBORw0KGgoAAAANSUhEUg==")
        await service.write_blob(tp)
        mock_backend.write_file.assert_called_once()
        call_path = mock_backend.write_file.call_args.args[0]
        assert call_path.endswith("image.png")

    @pytest.mark.asyncio
    async def test_no_image_file_without_base64(self, service, mock_backend):
        tp = _make_mock_timepoint(image_base64=None)
        await service.write_blob(tp)
        mock_backend.write_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_sequence_json_written(self, service, mock_backend):
        tp = _make_mock_timepoint(sequence_id="seq-001")
        await service.write_blob(tp, sequence_members=[{"id": "a", "slug": "a"}])
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "sequence.json" in filenames

    @pytest.mark.asyncio
    async def test_grounding_json_written(self, service, mock_backend):
        tp = _make_mock_timepoint(grounding_data_json={"facts": ["fact1"]})
        await service.write_blob(tp)
        write_calls = mock_backend.write_text.call_args_list
        filenames = [call.args[0].split("/")[-1] for call in write_calls]
        assert "grounding.json" in filenames


class TestReconstructBlob:
    """Tests for StorageService.reconstruct_blob()."""

    @pytest.mark.asyncio
    async def test_deletes_existing_blob_first(self, service, mock_backend):
        mock_backend.exists.return_value = True
        tp = _make_mock_timepoint(blob_path="/tmp/test_blobs/old")
        await service.reconstruct_blob(tp)
        mock_backend.delete_directory.assert_called_once_with("/tmp/test_blobs/old")

    @pytest.mark.asyncio
    async def test_writes_new_blob(self, service, mock_backend):
        tp = _make_mock_timepoint()
        path, name = await service.reconstruct_blob(tp)
        assert path.startswith("/tmp/test_blobs/")


class TestDeleteBlob:
    """Tests for StorageService.delete_blob()."""

    @pytest.mark.asyncio
    async def test_soft_delete_moves_to_trash(self, service, mock_backend):
        mock_backend.exists.return_value = True
        tp = _make_mock_timepoint(
            blob_path="/tmp/test_blobs/2026/02/test",
            blob_folder_name="test_20260209_abc",
        )
        trash_path = await service.delete_blob(tp, soft=True)
        assert trash_path is not None
        assert ".trash" in trash_path
        mock_backend.move_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_hard_delete_removes(self, service, mock_backend):
        mock_backend.exists.return_value = True
        tp = _make_mock_timepoint(blob_path="/tmp/test_blobs/2026/02/test")
        result = await service.delete_blob(tp, soft=False)
        assert result is None
        mock_backend.delete_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_blob_path_returns_none(self, service):
        tp = _make_mock_timepoint(blob_path=None)
        result = await service.delete_blob(tp)
        assert result is None

    @pytest.mark.asyncio
    async def test_nonexistent_path_returns_none(self, service, mock_backend):
        mock_backend.exists.return_value = False
        tp = _make_mock_timepoint(blob_path="/nonexistent")
        result = await service.delete_blob(tp)
        assert result is None
