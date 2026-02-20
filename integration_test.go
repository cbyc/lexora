//go:build integration

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	"personal-kb/services/rss/api"
	"personal-kb/services/rss/config"
	"personal-kb/services/rss/feed"
	"personal-kb/services/rss/logging"
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

	loggers, err := logging.Setup(dataDir)
	if err != nil {
		t.Fatalf("logging.Setup: %v", err)
	}
	defer loggers.Close()

	mux := http.NewServeMux()
	api.RegisterRoutes(mux, cfg, loggers)
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

	// Verify logs
	t.Run("info_log_has_entries", func(t *testing.T) {
		data, err := os.ReadFile(filepath.Join(dataDir, "info.log"))
		if err != nil {
			t.Fatalf("read info.log: %v", err)
		}
		if len(data) == 0 {
			t.Error("info.log should not be empty")
		}
	})
}
