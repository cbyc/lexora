package main

import (
	"context"
	"fmt"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"lexora-feed/api"
	"lexora-feed/config"
)

func main() {
	// Load configuration
	cfg, cfgErr := config.Load("")
	if cfgErr != nil {
		// Config file was malformed — we'll log the warning after logger init
		log.Printf("WARNING: %v — using defaults", cfgErr)
	}

	logger := slog.New(slog.NewTextHandler(os.Stdout, nil))

	if cfgErr != nil {
		logger.Warn("config.yaml malformed, using defaults", "error", cfgErr.Error())
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
		logger.Info("RSS service started", "addr", addr, "default_range", cfg.DefaultRange)
		fmt.Printf("RSS service listening on %s\n", addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("server error", "error", err.Error())
			log.Fatalf("server error: %v", err)
		}
	}()

	<-done
	fmt.Println("\nShutting down...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	server.Shutdown(ctx)

	logger.Info("RSS service shutdown")
	fmt.Println("Goodbye.")
}
