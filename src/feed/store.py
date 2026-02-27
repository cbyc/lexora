from pathlib import Path

import yaml

from src.feed.models import DuplicateFeedError, Feed


class YamlFeedStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def load_feeds(self) -> list[Feed]:
        if not self._path.exists():
            return []
        content = self._path.read_text()
        if not content.strip():
            return []
        data = yaml.safe_load(content)
        if not data or "feeds" not in data:
            return []
        return [Feed(name=f["name"], url=f["url"]) for f in data["feeds"]]

    def save_feeds(self, feeds: list[Feed]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"feeds": [{"name": f.name, "url": f.url} for f in feeds]}
        self._path.write_text(yaml.dump(data, default_flow_style=False))

    def add_feed(self, feed: Feed) -> None:
        feeds = self.load_feeds()
        for existing in feeds:
            if existing.url == feed.url:
                raise DuplicateFeedError(f"Feed with URL '{feed.url}' already exists")
        feeds.append(feed)
        self.save_feeds(feeds)

    def ensure_data_file(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(yaml.dump({"feeds": []}, default_flow_style=False))
