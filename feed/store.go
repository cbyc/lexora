package feed

import (
	"errors"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

var ErrDuplicateFeed = errors.New("feed URL already exists")

type Feed struct {
	Name string `yaml:"name" json:"name"`
	URL  string `yaml:"url" json:"url"`
}

type feedsFile struct {
	Feeds []Feed `yaml:"feeds"`
}

func LoadFeeds(path string) ([]Feed, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}
	if len(data) == 0 {
		return nil, nil
	}

	var ff feedsFile
	if err := yaml.Unmarshal(data, &ff); err != nil {
		return nil, err
	}
	return ff.Feeds, nil
}

func SaveFeeds(path string, feeds []Feed) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	ff := feedsFile{Feeds: feeds}
	data, err := yaml.Marshal(&ff)
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

func AddFeed(path string, feed Feed) error {
	existing, err := LoadFeeds(path)
	if err != nil {
		return err
	}
	for _, f := range existing {
		if f.URL == feed.URL {
			return ErrDuplicateFeed
		}
	}
	existing = append(existing, feed)
	return SaveFeeds(path, existing)
}

func EnsureDataDir(dataDir string) error {
	return os.MkdirAll(dataDir, 0755)
}
