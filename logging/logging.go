package logging

import (
	"io"
	"log/slog"
	"os"
	"path/filepath"
)

type Loggers struct {
	Error *slog.Logger
	Warn  *slog.Logger
	Info  *slog.Logger

	closers []io.Closer
}

func Setup(dataDir string) (*Loggers, error) {
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		return nil, err
	}

	errFile, err := openLog(filepath.Join(dataDir, "logs", "errors.log"))
	if err != nil {
		return nil, err
	}
	warnFile, err := openLog(filepath.Join(dataDir, "logs", "warnings.log"))
	if err != nil {
		errFile.Close()
		return nil, err
	}
	infoFile, err := openLog(filepath.Join(dataDir, "logs", "info.log"))
	if err != nil {
		errFile.Close()
		warnFile.Close()
		return nil, err
	}

	opts := &slog.HandlerOptions{
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			// Remove the level key since each file implies its level
			if a.Key == slog.LevelKey {
				return slog.Attr{}
			}
			return a
		},
	}

	return &Loggers{
		Error:   slog.New(slog.NewTextHandler(errFile, opts)),
		Warn:    slog.New(slog.NewTextHandler(warnFile, opts)),
		Info:    slog.New(slog.NewTextHandler(infoFile, opts)),
		closers: []io.Closer{errFile, warnFile, infoFile},
	}, nil
}

func (l *Loggers) Close() {
	for _, c := range l.closers {
		c.Close()
	}
}

func openLog(path string) (*os.File, error) {
	return os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
}
