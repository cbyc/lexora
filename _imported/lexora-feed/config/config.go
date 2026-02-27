package config

import (
	"errors"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	Host            string `mapstructure:"host"`
	Port            int    `mapstructure:"port"`
	MaxPostsPerFeed int    `mapstructure:"max_posts_per_feed"`
	FetchTimeoutSec int    `mapstructure:"fetch_timeout_sec"`
	DataFile        string `mapstructure:"data_file"`
	DefaultRange    string `mapstructure:"default_range"`
}

func setDefaults(v *viper.Viper) {
	v.SetDefault("host", "localhost")
	v.SetDefault("port", 9001)
	v.SetDefault("max_posts_per_feed", 50)
	v.SetDefault("fetch_timeout_sec", 10)
	v.SetDefault("data_file", "./data/feeds.yaml")
	v.SetDefault("default_range", "last_month")
}

func Load(configPath string) (*Config, error) {
	v := viper.New()

	// 1. Built-in defaults
	setDefaults(v)

	// 2. Config file (optional)
	var fileErr error
	if configPath != "" {
		v.SetConfigFile(configPath)
	} else {
		v.SetConfigName("config")
		v.SetConfigType("yaml")
		v.AddConfigPath(".")
	}
	if err := v.ReadInConfig(); err != nil {
		_, notFound := err.(viper.ConfigFileNotFoundError)
		if !notFound && !errors.Is(err, os.ErrNotExist) {
			// File exists but is malformed or unreadable
			fileErr = fmt.Errorf("config file error: %w", err)
			// Reset to defaults by creating a fresh viper
			setDefaults(v)
		}
		// File not found is fine — just use defaults
	}

	// 3. Environment variable overrides
	v.SetEnvPrefix("RSS")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("unmarshal config: %w", err)
	}

	return &cfg, fileErr
}
