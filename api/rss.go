package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"lexora-feed/config"
	"lexora-feed/feed"
)

func HandleGetRSS(cfg *config.Config, logger *slog.Logger, feedsPath string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		from, to, err := parseDateRange(q.Get("range"), q.Get("from"), q.Get("to"), cfg.DefaultRange)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		feeds, err := feed.LoadFeeds(feedsPath)
		if err != nil {
			logger.Error("failed to read feeds file", "path", feedsPath, "error", err.Error())
			http.Error(w, "internal server error", http.StatusInternalServerError)
			return
		}

		timeout := time.Duration(cfg.FetchTimeoutSec) * time.Second
		posts, feedErrs := feed.FetchAllFeeds(r.Context(), feeds, cfg.MaxPostsPerFeed, timeout)

		for _, fe := range feedErrs {
			logger.Error("feed fetch failed", "feed", fe.FeedName, "url", fe.URL, "error", fe.Err.Error())
		}

		if len(feedErrs) == len(feeds) && len(feeds) > 0 {
			w.Header().Set("X-Feed-Errors", "all-feeds-failed")
		}

		// Filter by date range
		var filtered []feed.Post
		for _, p := range posts {
			if !from.IsZero() && p.PublishedAt.Before(from) {
				continue
			}
			if !to.IsZero() && p.PublishedAt.After(to) {
				continue
			}
			filtered = append(filtered, p)
		}

		w.Header().Set("Content-Type", "application/json")
		if filtered == nil {
			filtered = []feed.Post{} // ensure JSON [] not null
		}
		json.NewEncoder(w).Encode(filtered)
	}
}

func HandlePutRSS(cfg *config.Config, logger *slog.Logger, feedsPath string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Name string `json:"name"`
			URL  string `json:"url"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid JSON body", http.StatusBadRequest)
			return
		}
		if req.Name == "" || req.URL == "" {
			http.Error(w, "name and url are required", http.StatusBadRequest)
			return
		}

		// Validate the feed URL
		ctx, cancel := context.WithTimeout(r.Context(), time.Duration(cfg.FetchTimeoutSec)*time.Second)
		defer cancel()
		if err := feed.ValidateFeed(ctx, req.Name, req.URL); err != nil {
			http.Error(w, fmt.Sprintf("URL is not a valid RSS/Atom feed: %v", err), http.StatusUnprocessableEntity)
			return
		}

		newFeed := feed.Feed{Name: req.Name, URL: req.URL}
		if err := feed.AddFeed(feedsPath, newFeed); err != nil {
			if errors.Is(err, feed.ErrDuplicateFeed) {
				logger.Warn("duplicate feed URL rejected", "url", req.URL)
				http.Error(w, "feed URL already exists", http.StatusConflict)
				return
			}
			logger.Error("failed to add feed", "error", err.Error())
			http.Error(w, "internal server error", http.StatusInternalServerError)
			return
		}

		logger.Info("feed added", "name", req.Name, "url", req.URL)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]any{
			"message": "Feed added successfully",
			"feed":    newFeed,
		})
	}
}

func parseDateRange(rangeParam, fromParam, toParam string, defaultRange string) (from, to time.Time, err error) {
	// Explicit from/to take precedence
	if fromParam != "" || toParam != "" {
		if fromParam != "" {
			from, err = time.Parse(time.RFC3339, fromParam)
			if err != nil {
				return time.Time{}, time.Time{}, fmt.Errorf("invalid 'from' parameter: %w", err)
			}
		}
		if toParam != "" {
			to, err = time.Parse(time.RFC3339, toParam)
			if err != nil {
				return time.Time{}, time.Time{}, fmt.Errorf("invalid 'to' parameter: %w", err)
			}
		}
		return from, to, nil
	}

	// Use range param or default
	r := rangeParam
	if r == "" {
		r = defaultRange
	}

	now := time.Now().UTC()
	startOfToday := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)

	switch r {
	case "today":
		return startOfToday, time.Time{}, nil
	case "last_week":
		return startOfToday.AddDate(0, 0, -7), time.Time{}, nil
	case "last_month":
		return startOfToday.AddDate(0, -1, 0), time.Time{}, nil
	case "last_3_months":
		return startOfToday.AddDate(0, -3, 0), time.Time{}, nil
	case "last_6_months":
		return startOfToday.AddDate(0, -6, 0), time.Time{}, nil
	case "last_year":
		return startOfToday.AddDate(-1, 0, 0), time.Time{}, nil
	default:
		return time.Time{}, time.Time{}, fmt.Errorf("invalid range: %q", r)
	}
}

func RegisterRoutes(mux *http.ServeMux, cfg *config.Config, logger *slog.Logger) {
	feedsPath := cfg.DataFile

	getHandler := HandleGetRSS(cfg, logger, feedsPath)
	putHandler := HandlePutRSS(cfg, logger, feedsPath)

	mux.HandleFunc("/rss", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			getHandler(w, r)
		case http.MethodPut:
			putHandler(w, r)
		case http.MethodOptions:
			w.WriteHeader(http.StatusNoContent)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}
