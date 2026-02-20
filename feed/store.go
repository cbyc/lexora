package feed

import (
	"errors"
	"os"

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

func EnsureDataFile(path string) error {
	// ensure the file exists and can be read
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			_, err := os.Create(path)
			return err
		}
		return err
	}

	// verify write permission is granted
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	_, err = f.Write(b)
	if err != nil {
		return err
	}
	return nil
}
