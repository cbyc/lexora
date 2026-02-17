package feed

import (
	"context"
	"fmt"
	"net/http"
	"sort"
	"sync"
	"time"

	"github.com/mmcdole/gofeed"
)

type Post struct {
	FeedName    string    `json:"feed_name"`
	Title       string    `json:"title"`
	URL         string    `json:"url"`
	PublishedAt time.Time `json:"published_at"`
}

type FeedError struct {
	FeedName string
	URL      string
	Err      error
}

func (e FeedError) Error() string {
	return fmt.Sprintf("feed %q (%s): %v", e.FeedName, e.URL, e.Err)
}

func FetchFeed(ctx context.Context, feedURL string, maxPosts int) ([]Post, error) {
	parser := gofeed.NewParser()
	parser.Client = &http.Client{
		Transport: http.DefaultTransport,
	}

	f, err := parser.ParseURLWithContext(feedURL, ctx)
	if err != nil {
		return nil, err
	}

	var posts []Post
	for i, item := range f.Items {
		if i >= maxPosts {
			break
		}
		published := time.Time{}
		if item.PublishedParsed != nil {
			published = item.PublishedParsed.UTC()
		} else if item.UpdatedParsed != nil {
			published = item.UpdatedParsed.UTC()
		}

		posts = append(posts, Post{
			FeedName:    f.Title,
			Title:       item.Title,
			URL:         item.Link,
			PublishedAt: published,
		})
	}
	return posts, nil
}

func ValidateFeed(ctx context.Context, url string) error {
	_, err := FetchFeed(ctx, url, 1)
	return err
}

func FetchAllFeeds(ctx context.Context, feeds []Feed, maxPostsPerFeed int, timeout time.Duration) ([]Post, []FeedError) {
	var (
		mu       sync.Mutex
		allPosts []Post
		errs     []FeedError
		wg       sync.WaitGroup
	)

	for _, f := range feeds {
		wg.Add(1)
		go func(fd Feed) {
			defer wg.Done()
			fetchCtx, cancel := context.WithTimeout(ctx, timeout)
			defer cancel()

			posts, err := FetchFeed(fetchCtx, fd.URL, maxPostsPerFeed)
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				errs = append(errs, FeedError{FeedName: fd.Name, URL: fd.URL, Err: err})
				return
			}
			// Override feed name with the user-configured name
			for i := range posts {
				posts[i].FeedName = fd.Name
			}
			allPosts = append(allPosts, posts...)
		}(f)
	}

	wg.Wait()

	sort.Slice(allPosts, func(i, j int) bool {
		return allPosts[i].PublishedAt.After(allPosts[j].PublishedAt)
	})

	return allPosts, errs
}
