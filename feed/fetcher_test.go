package feed

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

const sampleRSS = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Post One</title>
      <link>https://example.com/1</link>
      <pubDate>Mon, 16 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Post Two</title>
      <link>https://example.com/2</link>
      <pubDate>Sun, 15 Feb 2026 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Post Three</title>
      <link>https://example.com/3</link>
      <pubDate>Sat, 14 Feb 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>`

func TestFetchFeed_ValidRSS(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/rss+xml")
		fmt.Fprint(w, sampleRSS)
	}))
	defer srv.Close()

	testFeedName := "Hot Feed"
	posts, err := FetchFeed(context.Background(), testFeedName, srv.URL, 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(posts) != 2 {
		t.Fatalf("expected 2 posts (maxPosts=2), got %d", len(posts))
	}
	if posts[0].Title != "Post One" {
		t.Errorf("posts[0].Title = %q, want %q", posts[0].Title, "Post One")
	}
	if posts[0].FeedName != testFeedName {
		t.Errorf("posts[0].FeedName = %q, want %q", posts[0].FeedName, testFeedName)
	}
	if posts[0].URL != "https://example.com/1" {
		t.Errorf("posts[0].URL = %q, want %q", posts[0].URL, "https://example.com/1")
	}
	if posts[0].PublishedAt.IsZero() {
		t.Error("posts[0].PublishedAt should not be zero")
	}
}

func TestFetchFeed_InvalidContent(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprint(w, "<html><body>Not a feed</body></html>")
	}))
	defer srv.Close()

	_, err := FetchFeed(context.Background(), "", srv.URL, 10)
	if err == nil {
		t.Error("expected error for non-feed content, got nil")
	}
}

func TestFetchFeed_Timeout(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(2 * time.Second)
		fmt.Fprint(w, sampleRSS)
	}))
	defer srv.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	_, err := FetchFeed(ctx, "", srv.URL, 10)
	if err == nil {
		t.Error("expected timeout error, got nil")
	}
}

func TestValidateFeed_Valid(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, sampleRSS)
	}))
	defer srv.Close()

	err := ValidateFeed(context.Background(), "", srv.URL)
	if err != nil {
		t.Errorf("expected nil error, got: %v", err)
	}
}

func TestValidateFeed_NotAFeed(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "<html><body>Hello</body></html>")
	}))
	defer srv.Close()

	err := ValidateFeed(context.Background(), "", srv.URL)
	if err == nil {
		t.Error("expected error for non-feed URL, got nil")
	}
}

func TestFetchAllFeeds_AllSucceed(t *testing.T) {
	srv1 := newFeedServer("Feed A", "2026-02-16T10:00:00Z")
	defer srv1.Close()
	srv2 := newFeedServer("Feed B", "2026-02-17T10:00:00Z")
	defer srv2.Close()

	feeds := []Feed{
		{Name: "A", URL: srv1.URL},
		{Name: "B", URL: srv2.URL},
	}

	posts, errs := FetchAllFeeds(context.Background(), feeds, 50, 5*time.Second)
	if len(errs) != 0 {
		t.Errorf("expected no errors, got %v", errs)
	}
	if len(posts) != 2 {
		t.Fatalf("expected 2 posts, got %d", len(posts))
	}
	// Should be sorted newest first
	if posts[0].FeedName != "B" {
		t.Errorf("expected newest post from Feed B first, got %q", posts[0].FeedName)
	}
}

func TestFetchAllFeeds_PartialFailure(t *testing.T) {
	srv := newFeedServer("Good Feed", "2026-02-16T10:00:00Z")
	defer srv.Close()
	badSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer badSrv.Close()

	feeds := []Feed{
		{Name: "Good", URL: srv.URL},
		{Name: "Bad", URL: badSrv.URL},
	}

	posts, errs := FetchAllFeeds(context.Background(), feeds, 50, 5*time.Second)
	if len(errs) != 1 {
		t.Errorf("expected 1 error, got %d", len(errs))
	}
	if len(posts) != 1 {
		t.Errorf("expected 1 post from successful feed, got %d", len(posts))
	}
}

func TestFetchAllFeeds_AllFail(t *testing.T) {
	badSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer badSrv.Close()

	feeds := []Feed{
		{Name: "Bad1", URL: badSrv.URL},
		{Name: "Bad2", URL: badSrv.URL + "/other"},
	}

	posts, errs := FetchAllFeeds(context.Background(), feeds, 50, 5*time.Second)
	if len(errs) == 0 {
		t.Error("expected errors, got none")
	}
	if len(posts) != 0 {
		t.Errorf("expected 0 posts, got %d", len(posts))
	}
}

func newFeedServer(title, pubDate string) *httptest.Server {
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
</rss>`, title, title, title, pubDate)

	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, rss)
	}))
}
