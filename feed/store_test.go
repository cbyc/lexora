package feed

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestLoadFeeds_NotExists(t *testing.T) {
	feeds, err := LoadFeeds("/nonexistent/feeds.yaml")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(feeds) != 0 {
		t.Errorf("expected empty slice, got %d feeds", len(feeds))
	}
}

func TestLoadFeeds_ValidYAML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "feeds.yaml")
	content := []byte(`feeds:
  - name: Test Feed
    url: https://example.com/rss
  - name: Another
    url: https://another.com/feed
`)
	os.WriteFile(path, content, 0644)

	feeds, err := LoadFeeds(path)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(feeds) != 2 {
		t.Fatalf("expected 2 feeds, got %d", len(feeds))
	}
	if feeds[0].Name != "Test Feed" {
		t.Errorf("feeds[0].Name = %q, want %q", feeds[0].Name, "Test Feed")
	}
	if feeds[1].URL != "https://another.com/feed" {
		t.Errorf("feeds[1].URL = %q, want %q", feeds[1].URL, "https://another.com/feed")
	}
}

func TestLoadFeeds_EmptyFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "feeds.yaml")
	os.WriteFile(path, []byte(""), 0644)

	feeds, err := LoadFeeds(path)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(feeds) != 0 {
		t.Errorf("expected empty slice, got %d feeds", len(feeds))
	}
}

func TestSaveFeeds_WritesCorrectYAML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "feeds.yaml")
	feeds := []Feed{
		{Name: "A", URL: "https://a.com/rss"},
		{Name: "B", URL: "https://b.com/rss"},
	}

	if err := SaveFeeds(path, feeds); err != nil {
		t.Fatalf("SaveFeeds failed: %v", err)
	}

	// Round-trip
	loaded, err := LoadFeeds(path)
	if err != nil {
		t.Fatalf("LoadFeeds failed: %v", err)
	}
	if len(loaded) != 2 {
		t.Fatalf("expected 2 feeds, got %d", len(loaded))
	}
	if loaded[0].Name != "A" || loaded[1].Name != "B" {
		t.Errorf("unexpected feeds: %+v", loaded)
	}
}

func TestSaveFeeds_CreatesParentDirs(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nested", "deep", "feeds.yaml")

	err := SaveFeeds(path, []Feed{{Name: "X", URL: "https://x.com"}})
	if err != nil {
		t.Fatalf("SaveFeeds failed: %v", err)
	}
	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Error("expected file to be created")
	}
}

func TestAddFeed_NewFeed(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "feeds.yaml")
	SaveFeeds(path, []Feed{{Name: "Existing", URL: "https://existing.com"}})

	err := AddFeed(path, Feed{Name: "New", URL: "https://new.com"})
	if err != nil {
		t.Fatalf("AddFeed failed: %v", err)
	}

	feeds, _ := LoadFeeds(path)
	if len(feeds) != 2 {
		t.Fatalf("expected 2 feeds, got %d", len(feeds))
	}
	if feeds[1].Name != "New" {
		t.Errorf("feeds[1].Name = %q, want %q", feeds[1].Name, "New")
	}
}

func TestAddFeed_DuplicateURL(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "feeds.yaml")
	SaveFeeds(path, []Feed{{Name: "Existing", URL: "https://existing.com"}})

	err := AddFeed(path, Feed{Name: "Dup", URL: "https://existing.com"})
	if !errors.Is(err, ErrDuplicateFeed) {
		t.Errorf("expected ErrDuplicateFeed, got: %v", err)
	}
}

func TestAddFeed_CreatesFileIfMissing(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "data", "feeds.yaml")

	err := AddFeed(path, Feed{Name: "First", URL: "https://first.com"})
	if err != nil {
		t.Fatalf("AddFeed failed: %v", err)
	}

	feeds, _ := LoadFeeds(path)
	if len(feeds) != 1 {
		t.Fatalf("expected 1 feed, got %d", len(feeds))
	}
}

func TestInitFeedsFile_CreatesWithSeeds(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "data", "feeds.yaml")

	err := InitFeedsFile(path, SeedFeeds)
	if err != nil {
		t.Fatalf("InitFeedsFile failed: %v", err)
	}

	feeds, err := LoadFeeds(path)
	if err != nil {
		t.Fatalf("LoadFeeds failed: %v", err)
	}
	if len(feeds) != 3 {
		t.Fatalf("expected 3 seed feeds, got %d", len(feeds))
	}
	if feeds[0].Name != "Hacker News" {
		t.Errorf("feeds[0].Name = %q, want %q", feeds[0].Name, "Hacker News")
	}
}

func TestInitFeedsFile_ExistingFileUntouched(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "feeds.yaml")
	// Write a custom file first
	SaveFeeds(path, []Feed{{Name: "Custom", URL: "https://custom.com"}})

	// InitFeedsFile should NOT overwrite
	err := InitFeedsFile(path, SeedFeeds)
	if err != nil {
		t.Fatalf("InitFeedsFile failed: %v", err)
	}

	feeds, _ := LoadFeeds(path)
	if len(feeds) != 1 {
		t.Fatalf("expected 1 feed (untouched), got %d", len(feeds))
	}
	if feeds[0].Name != "Custom" {
		t.Errorf("feeds[0].Name = %q, want %q", feeds[0].Name, "Custom")
	}
}
