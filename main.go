package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"lexora-feed/api"
	"lexora-feed/config"
	"lexora-feed/feed"
)

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stdout, nil))

	// Load configuration
	cfg, cfgErr := config.Load("")
	if cfgErr != nil {
		logger.Warn("config.yaml malformed, using defaults", "error", cfgErr.Error())
	}

	if err := feed.EnsureDataFile(cfg.DataFile); err != nil {
		logger.Error("Cannot access the feed data file.", "error", err)
		return
	}

	// Register routes
	mux := http.NewServeMux()
	api.RegisterRoutes(mux, cfg, logger)

	// Wrap with CORS
	handler := api.CORS(mux)

	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	server := &http.Server{
		Addr:    addr,
		Handler: handler,
	}

	// Graceful shutdown
	done := make(chan os.Signal, 1)
	signal.Notify(done, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		logger.Info("RSS service started", "addr", addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("server startup error", "error", err.Error())
		}
	}()

	<-done
	logger.Info("\nShutting down...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		logger.Error("server shutdown error", "error", err.Error())
	}

	logger.Info("RSS service shutdown")
}
