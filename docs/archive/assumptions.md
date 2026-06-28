# Assumptions

- This repository starts as a new Python project with no existing application code.
- The initial implementation verifies the framework through sample site definitions and local fixture HTML, not real media site crawling.
- Dates are stored as extracted strings. Advanced date normalization is intentionally deferred.
- `max_pages` and `next_page_selector` are stored in site config, but multi-page crawling is deferred.
- Playwright-required sites are skipped and recorded in `crawl_skips` when global Playwright is disabled.
- Legal, terms-of-service, authentication, CAPTCHA, or article-body requirements should stop implementation for explicit human review.
