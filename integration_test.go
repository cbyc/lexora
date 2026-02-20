//go:build integration

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"path/filepath"
	"testing"
	"time"

	"lexora-feed/api"
	"lexora-feed/config"
	"lexora-feed/feed"
)

func TestIntegration_Smoke(t *testing.T) {
	dir := t.TempDir()
	dataDir := filepath.Join(dir, "data")

	cfg := &config.Config{
		Host:            "localhost",
		Port:            0,
		MaxPostsPerFeed: 50,
		FetchTimeoutSec: 10,
		DataFile:        filepath.Join(dataDir, "feeds.yaml"),
		DefaultRange:    "last_month",
	}

	if err := feed.EnsureDataDir(dataDir); err != nil {
		t.Fatalf("EnsureDataDir: %v", err)
	}

	logger := slog.New(slog.NewTextHandler(io.Discard, nil))

	mux := http.NewServeMux()
	api.RegisterRoutes(mux, cfg, logger)
	handler := api.CORS(mux)

	ln, err := net.Listen("tcp", "localhost:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()

	server := &http.Server{Handler: handler}
	go server.Serve(ln)
	defer server.Close()

	base := fmt.Sprintf("http://%s", ln.Addr().String())
	client := &http.Client{Timeout: 15 * time.Second}

	// GET /rss?range=last_month
	t.Run("GET_last_month", func(t *testing.T) {
		resp, err := client.Get(base + "/rss?range=last_month")
		if err != nil {
			t.Fatalf("GET: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != 200 {
			body, _ := io.ReadAll(resp.Body)
			t.Fatalf("status=%d body=%s", resp.StatusCode, body)
		}
		var posts []feed.Post
		json.NewDecoder(resp.Body).Decode(&posts)
		t.Logf("got %d posts", len(posts))
	})

	// PUT /rss — add new feed
	t.Run("PUT_new_feed", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{
			"name": "Lobsters",
			"url":  "https://lobste.rs/rss",
		})
		req, _ := http.NewRequest(http.MethodPut, base+"/rss", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		res, err := client.Do(req)
		if err != nil {
			t.Fatalf("PUT: %v", err)
		}
		defer res.Body.Close()
		if res.StatusCode != 201 {
			resBody, _ := io.ReadAll(res.Body)
			t.Fatalf("status=%d body=%s", res.StatusCode, resBody)
		}
	})

	// PUT /rss duplicate → 409
	t.Run("PUT_duplicate", func(t *testing.T) {
		body, _ := json.Marshal(map[string]string{
			"name": "Lobsters Again",
			"url":  "https://lobste.rs/rss",
		})
		req, _ := http.NewRequest(http.MethodPut, base+"/rss", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		res, err := client.Do(req)
		if err != nil {
			t.Fatalf("PUT: %v", err)
		}
		defer res.Body.Close()
		if res.StatusCode != 409 {
			t.Errorf("status=%d, want 409", res.StatusCode)
		}
	})

	// GET /rss?range=invalid → 400
	t.Run("GET_invalid_range", func(t *testing.T) {
		resp, err := client.Get(base + "/rss?range=invalid")
		if err != nil {
			t.Fatalf("GET: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != 400 {
			t.Errorf("status=%d, want 400", resp.StatusCode)
		}
	})

}
