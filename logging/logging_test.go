package logging

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSetup_CreatesFiles(t *testing.T) {
	dir := t.TempDir()
	loggers, err := Setup(dir)
	if err != nil {
		t.Fatalf("Setup failed: %v", err)
	}
	defer loggers.Close()

	for _, name := range []string{"errors.log", "warnings.log", "info.log"} {
		path := filepath.Join(dir, name)
		if _, err := os.Stat(path); os.IsNotExist(err) {
			t.Errorf("expected %s to exist", name)
		}
	}
}

func TestError_WritesToErrorsLog(t *testing.T) {
	dir := t.TempDir()
	loggers, err := Setup(dir)
	if err != nil {
		t.Fatalf("Setup failed: %v", err)
	}

	loggers.Error.Error("feed fetch failed", "feed", "HN", "url", "https://example.com")
	loggers.Close()

	content := readFile(t, filepath.Join(dir, "errors.log"))
	if !strings.Contains(content, "feed fetch failed") {
		t.Errorf("errors.log missing message, got: %s", content)
	}
	if !strings.Contains(content, "feed=HN") {
		t.Errorf("errors.log missing feed attr, got: %s", content)
	}

	// Should NOT appear in other logs
	assertEmpty(t, filepath.Join(dir, "warnings.log"))
	assertEmpty(t, filepath.Join(dir, "info.log"))
}

func TestWarn_WritesToWarningsLog(t *testing.T) {
	dir := t.TempDir()
	loggers, err := Setup(dir)
	if err != nil {
		t.Fatalf("Setup failed: %v", err)
	}

	loggers.Warn.Warn("config malformed")
	loggers.Close()

	content := readFile(t, filepath.Join(dir, "warnings.log"))
	if !strings.Contains(content, "config malformed") {
		t.Errorf("warnings.log missing message, got: %s", content)
	}

	assertEmpty(t, filepath.Join(dir, "errors.log"))
	assertEmpty(t, filepath.Join(dir, "info.log"))
}

func TestInfo_WritesToInfoLog(t *testing.T) {
	dir := t.TempDir()
	loggers, err := Setup(dir)
	if err != nil {
		t.Fatalf("Setup failed: %v", err)
	}

	loggers.Info.Info("service started", "addr", "localhost:9001")
	loggers.Close()

	content := readFile(t, filepath.Join(dir, "info.log"))
	if !strings.Contains(content, "service started") {
		t.Errorf("info.log missing message, got: %s", content)
	}
	if !strings.Contains(content, "addr=localhost:9001") {
		t.Errorf("info.log missing addr attr, got: %s", content)
	}

	assertEmpty(t, filepath.Join(dir, "errors.log"))
	assertEmpty(t, filepath.Join(dir, "warnings.log"))
}

func TestLogFormat(t *testing.T) {
	dir := t.TempDir()
	loggers, err := Setup(dir)
	if err != nil {
		t.Fatalf("Setup failed: %v", err)
	}

	loggers.Info.Info("test message", "key", "value")
	loggers.Close()

	content := readFile(t, filepath.Join(dir, "info.log"))
	// Should contain timestamp (time=...)
	if !strings.Contains(content, "time=") {
		t.Errorf("log line missing timestamp, got: %s", content)
	}
	// Should contain the key=value attribute
	if !strings.Contains(content, "key=value") {
		t.Errorf("log line missing key=value, got: %s", content)
	}
	// Should contain the message
	if !strings.Contains(content, "msg=\"test message\"") {
		t.Errorf("log line missing msg, got: %s", content)
	}
}

func readFile(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read %s: %v", path, err)
	}
	return string(data)
}

func assertEmpty(t *testing.T, path string) {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("failed to stat %s: %v", path, err)
	}
	if info.Size() != 0 {
		t.Errorf("expected %s to be empty, size=%d", path, info.Size())
	}
}
