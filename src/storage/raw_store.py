import json
import os
from datetime import datetime, timezone

from src.models.domain import RawAuctionItem
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RawStore:
    """
    Store raw crawl responses to local filesystem.
    Structure: data/raw/{source_id}/{YYYY-MM-DD}/page_{n}.json
    Allows re-parsing without re-crawling.
    """

    def __init__(self, base_dir: str = "data/raw"):
        self._base_dir = base_dir

    def save_page(self, source_id: str, page: int, data: list[dict]):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dir_path = os.path.join(self._base_dir, source_id, today)
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, f"page_{page}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.debug("Saved raw page", source=source_id, page=page, path=file_path)
        return file_path

    def save_item(self, item: RawAuctionItem) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dir_path = os.path.join(self._base_dir, item.source_id.value, today, "items")
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, f"{item.source_item_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(item.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        return file_path

    def save_api_response(self, source_id: str, endpoint: str, data) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_endpoint = endpoint.replace("/", "_").replace("?", "_").strip("_")
        dir_path = os.path.join(self._base_dir, source_id, today, "api")
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, f"{safe_endpoint}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        return file_path

    def load_checkpoint(self, source_id: str) -> dict:
        path = os.path.join(self._base_dir, source_id, "checkpoint.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_checkpoint(self, source_id: str, data: dict):
        dir_path = os.path.join(self._base_dir, source_id)
        os.makedirs(dir_path, exist_ok=True)

        path = os.path.join(dir_path, "checkpoint.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info("Checkpoint saved", source=source_id, data=data)
