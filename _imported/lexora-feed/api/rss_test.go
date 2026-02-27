package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"lexora-feed/config"
	"lexora-feed/feed"
)

// --- parseDateRange tests ---

func TestParseDateRange_ExplicitFromTo(t *testing.T) {
	from, to, err := parseDateRange("", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "last_month")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if from.Year() != 2026 || from.Month() != 1 {
		t.Errorf("from = %v, want 2026-01", from)
	}
	if to.Year() != 2026 || to.Month() != 2 {
		t.Errorf("to = %v, want 2026-02", to)
	}
}

func TestParseDateRange_RangeShorthand(t *testing.T) {
	cases := []string{"today", "last_week", "last_month", "last_3_months", "last_6_months", "last_year"}
	for _, r := range cases {
		from, _, err := parseDateRange(r, "", "", "last_month")
		if err != nil {
			t.Errorf("range=%q: unexpected error: %v", r, err)
		}
		if from.IsZero() {
			t.Errorf("range=%q: from should not be zero", r)
		}
	}
}

func TestParseDateRange_Default(t *testing.T) {
	from, _, err := parseDateRange("", "", "", "last_month")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if from.IsZero() {
		t.Error("expected non-zero from when using default range")
	}
}

func TestParseDateRange_Invalid(t *testing.T) {
	_, _, err := parseDateRange("bogus", "", "", "last_month")
	if err == nil {
		t.Error("expected error for invalid range, got nil")
	}
}

func TestParseDateRange_AllTime(t *testing.T) {
	// "All time" in the UI sends no range param, but the default is last_month.
	// To get all time, the client must explicitly send from/to as empty — which
	// means the server uses the default. True "all time" requires a specific
	// handling. For now, we test that from/to override works.
	from, to, err := parseDateRange("", "2020-01-01T00:00:00Z", "", "last_month")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if from.Year() != 2020 {
		t.Errorf("from = %v, want 2020", from)
	}
	if !to.IsZero() {
		t.Errorf("to should be zero when not provided, got %v", to)
	}
}

// --- Handler tests ---

func setupTest(t *testing.T) (*config.Config, *slog.Logger) {
	t.Helper()
	dir := t.TempDir()
	dataDir := filepath.Join(dir, "data")
	os.MkdirAll(dataDir, 0755)

	cfg := &config.Config{
		Host:            "localhost",
		Port:            9001,
		MaxPostsPerFeed: 50,
		FetchTimeoutSec: 5,
		DataFile:        filepath.Join(dataDir, "feeds.yaml"),
		DefaultRange:    "last_month",
	}

	logger := slog.New(slog.NewTextHandler(io.Discard, nil))

	return cfg, logger
}

func newFeedServer(title, pubDateRFC2822 string) *httptest.Server {
	rss := fmt.Sprintf(`<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>%s</title>
    <item>
      <title>Post from %s</title>
      <link>https://example.com/%s</link>
      <pubDate>%s</pubDate>
    </item>
  </channel>
</rss>`, title, title, title, pubDateRFC2822)

	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, rss)
	}))
}

func TestGetRSS_Success(t *testing.T) {
	cfg, logger := setupTest(t)

	srv := newFeedServer("TestFeed", time.Now().UTC().Format(time.RFC1123Z))
	defer srv.Close()

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{{Name: "TestFeed", URL: srv.URL}})

	req := httptest.NewRequest(http.MethodGet, "/rss?range=last_month", nil)
	w := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 200 {
		t.Errorf("status = %d, want 200", w.Code)
	}

	var posts []feed.Post
	json.NewDecoder(w.Body).Decode(&posts)
	if len(posts) == 0 {
		t.Error("expected at least 1 post")
	}
}

func TestGetRSS_WithDateFilter(t *testing.T) {
	cfg, logger := setupTest(t)

	// Create a feed with a post from a year ago
	srv := newFeedServer("OldFeed", "Mon, 01 Jan 2025 10:00:00 +0000")
	defer srv.Close()

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{{Name: "OldFeed", URL: srv.URL}})

	req := httptest.NewRequest(http.MethodGet, "/rss?range=last_week", nil)
	w := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 200 {
		t.Errorf("status = %d, want 200", w.Code)
	}

	var posts []feed.Post
	json.NewDecoder(w.Body).Decode(&posts)
	if len(posts) != 0 {
		t.Errorf("expected 0 posts (old post filtered out), got %d", len(posts))
	}
}

func TestGetRSS_NoFeeds(t *testing.T) {
	cfg, logger := setupTest(t)

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{})

	req := httptest.NewRequest(http.MethodGet, "/rss?range=last_month", nil)
	w := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 200 {
		t.Errorf("status = %d, want 200", w.Code)
	}

	var posts []feed.Post
	json.NewDecoder(w.Body).Decode(&posts)
	if len(posts) != 0 {
		t.Errorf("expected 0 posts, got %d", len(posts))
	}
}

func TestGetRSS_InvalidRange(t *testing.T) {
	cfg, logger := setupTest(t)

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{})

	req := httptest.NewRequest(http.MethodGet, "/rss?range=bogus", nil)
	w := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 400 {
		t.Errorf("status = %d, want 400", w.Code)
	}
}

func TestGetRSS_AllFeedsFail(t *testing.T) {
	cfg, logger := setupTest(t)

	badSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer badSrv.Close()

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{{Name: "Bad", URL: badSrv.URL}})

	req := httptest.NewRequest(http.MethodGet, "/rss?range=last_month", nil)
	w := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 200 {
		t.Errorf("status = %d, want 200", w.Code)
	}
	if w.Header().Get("X-Feed-Errors") != "all-feeds-failed" {
		t.Error("expected X-Feed-Errors header")
	}
}

func TestGetRSS_FeedsFileUnreadable(t *testing.T) {
	cfg, logger := setupTest(t)

	// Point to a directory instead of a file
	req := httptest.NewRequest(http.MethodGet, "/rss?range=last_month", nil)
	w := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, "/nonexistent-dir-xyz/feeds.yaml")(w, req)

	// LoadFeeds returns nil, nil for non-existent file, so this should be 200 with empty array
	// Let's point to a path that will fail differently — a directory
	w2 := httptest.NewRecorder()
	HandleGetRSS(cfg, logger, os.TempDir())(w2, req)
	// Reading a directory as a file should fail
	if w2.Code != 500 {
		t.Errorf("status = %d, want 500", w2.Code)
	}
}

func TestPutRSS_Success(t *testing.T) {
	cfg, logger := setupTest(t)

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{})

	// Create a valid feed server
	srv := newFeedServer("NewFeed", time.Now().UTC().Format(time.RFC1123Z))
	defer srv.Close()

	body, _ := json.Marshal(map[string]string{"name": "NewFeed", "url": srv.URL})
	req := httptest.NewRequest(http.MethodPut, "/rss", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	HandlePutRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 201 {
		t.Errorf("status = %d, want 201, body: %s", w.Code, w.Body.String())
	}

	// Verify feed was persisted
	feeds, _ := feed.LoadFeeds(cfg.DataFile)
	if len(feeds) != 1 {
		t.Errorf("expected 1 feed in file, got %d", len(feeds))
	}
}

func TestPutRSS_MissingFields(t *testing.T) {
	cfg, logger := setupTest(t)

	body, _ := json.Marshal(map[string]string{"name": "NoURL"})
	req := httptest.NewRequest(http.MethodPut, "/rss", bytes.NewReader(body))
	w := httptest.NewRecorder()
	HandlePutRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 400 {
		t.Errorf("status = %d, want 400", w.Code)
	}
}

func TestPutRSS_DuplicateURL(t *testing.T) {
	cfg, logger := setupTest(t)

	srv := newFeedServer("Dup", time.Now().UTC().Format(time.RFC1123Z))
	defer srv.Close()

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{{Name: "Existing", URL: srv.URL}})

	body, _ := json.Marshal(map[string]string{"name": "Dup", "url": srv.URL})
	req := httptest.NewRequest(http.MethodPut, "/rss", bytes.NewReader(body))
	w := httptest.NewRecorder()
	HandlePutRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 409 {
		t.Errorf("status = %d, want 409", w.Code)
	}
}

func TestPutRSS_InvalidFeedURL(t *testing.T) {
	cfg, logger := setupTest(t)

	feed.SaveFeeds(cfg.DataFile, []feed.Feed{})

	// Server that returns HTML, not a feed
	htmlSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "<html><body>Not a feed</body></html>")
	}))
	defer htmlSrv.Close()

	body, _ := json.Marshal(map[string]string{"name": "Bad", "url": htmlSrv.URL})
	req := httptest.NewRequest(http.MethodPut, "/rss", bytes.NewReader(body))
	w := httptest.NewRecorder()
	HandlePutRSS(cfg, logger, cfg.DataFile)(w, req)

	if w.Code != 422 {
		t.Errorf("status = %d, want 422", w.Code)
	}
}
