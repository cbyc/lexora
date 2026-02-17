package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"personal-kb/services/rss/api"
	"personal-kb/services/rss/config"
	"personal-kb/services/rss/feed"
	"personal-kb/services/rss/logging"
)

func main() {
	// Load configuration
	cfg, cfgErr := config.Load("")
	if cfgErr != nil {
		// Config file was malformed — we'll log the warning after logger init
		log.Printf("WARNING: %v — using defaults", cfgErr)
	}

	// Initialize logging
	if err := feed.EnsureDataDir(cfg.DataDir); err != nil {
		log.Fatalf("failed to create data dir: %v", err)
	}

	loggers, err := logging.Setup(cfg.DataDir)
	if err != nil {
		log.Fatalf("failed to setup logging: %v", err)
	}
	defer loggers.Close()

	if cfgErr != nil {
		loggers.Warn.Warn("config.yaml malformed, using defaults", "error", cfgErr.Error())
	}

	// Initialize feeds file with seed data
	feedsPath := filepath.Join(cfg.DataDir, "feeds.yaml")
	if err := feed.InitFeedsFile(feedsPath, feed.SeedFeeds); err != nil {
		log.Fatalf("failed to initialize feeds file: %v", err)
	}

	// Register routes
	mux := http.NewServeMux()
	api.RegisterRoutes(mux, cfg, loggers)

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
		loggers.Info.Info("RSS service started", "addr", addr, "default_range", cfg.DefaultRange)
		fmt.Printf("RSS service listening on %s\n", addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			loggers.Error.Error("server error", "error", err.Error())
			log.Fatalf("server error: %v", err)
		}
	}()

	<-done
	fmt.Println("\nShutting down...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	server.Shutdown(ctx)

	loggers.Info.Info("RSS service shutdown")
	fmt.Println("Goodbye.")
}
