"""Command line interface for news monitor."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from news_monitor import database
from news_monitor.config import load_app_config, load_keywords, load_sites
from news_monitor.crawler import Crawler
from news_monitor.reporter import generate_report


LOGGER = logging.getLogger(__name__)


def _enable_system_trust_store() -> None:
    """Use the OS certificate store for HTTPS when truststore is installed."""

    try:
        import truststore
    except ImportError:
        return

    try:
        truststore.inject_into_ssl()
    except Exception as exc:  # pragma: no cover - environment dependent
        LOGGER.warning("Could not enable system trust store: %s", exc)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="news-monitor")
    parser.add_argument("--log-level", default="INFO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db")
    init_db.add_argument("--db", required=True, type=Path)

    import_config = subparsers.add_parser("import-config")
    import_config.add_argument("--db", required=True, type=Path)
    import_config.add_argument("--app-config", required=True, type=Path)
    import_config.add_argument("--keywords", required=True, type=Path)
    import_config.add_argument("--sites", required=True, type=Path)

    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--db", required=True, type=Path)
    crawl.add_argument("--app-config", required=True, type=Path)
    crawl.add_argument("--enable-playwright", action="store_true")
    crawl.add_argument("--site-id", action="append")
    crawl.add_argument("--candidate-keyword-id", action="append")
    crawl.add_argument("--max-sites", type=int)
    crawl.add_argument("--max-keywords", type=int)
    crawl.add_argument("--max-concurrent-sites", type=int)
    crawl.add_argument("--max-concurrent-playwright-sites", type=int)

    report = subparsers.add_parser("report")
    report.add_argument("--db", required=True, type=Path)
    report.add_argument("--date", required=True)
    report.add_argument("--output-dir", type=Path)

    crawl_report = subparsers.add_parser("crawl-and-report")
    crawl_report.add_argument("--db", required=True, type=Path)
    crawl_report.add_argument("--app-config", required=True, type=Path)
    crawl_report.add_argument("--date", required=True)
    crawl_report.add_argument("--enable-playwright", action="store_true")
    crawl_report.add_argument("--site-id", action="append")
    crawl_report.add_argument("--candidate-keyword-id", action="append")
    crawl_report.add_argument("--max-sites", type=int)
    crawl_report.add_argument("--max-keywords", type=int)
    crawl_report.add_argument("--max-concurrent-sites", type=int)
    crawl_report.add_argument("--max-concurrent-playwright-sites", type=int)
    return parser


def _override_concurrency(app_config, args) -> None:
    """Apply optional CLI concurrency overrides to the frozen config object."""

    if args.max_concurrent_sites is not None:
        object.__setattr__(
            app_config.crawler, "max_concurrent_sites", args.max_concurrent_sites
        )
    if args.max_concurrent_playwright_sites is not None:
        object.__setattr__(
            app_config.crawler,
            "max_concurrent_playwright_sites",
            args.max_concurrent_playwright_sites,
        )


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper()))
    _enable_system_trust_store()

    if args.command == "init-db":
        with database.connect(args.db) as conn:
            database.init_db(conn)
        return 0

    if args.command == "import-config":
        # app.yaml is loaded here to fail fast on invalid application config.
        load_app_config(args.app_config)
        with database.connect(args.db) as conn:
            database.init_db(conn)
            database.import_keywords(conn, load_keywords(args.keywords))
            database.import_sites(conn, load_sites(args.sites))
        return 0

    if args.command == "crawl":
        app_config = load_app_config(args.app_config)
        if args.enable_playwright:
            object.__setattr__(app_config.playwright, "enabled", True)
        _override_concurrency(app_config, args)
        with database.connect(args.db) as conn:
            database.init_db(conn)
            Crawler(
                conn,
                app_config,
                site_ids=set(args.site_id) if args.site_id else None,
                candidate_keyword_ids=set(args.candidate_keyword_id)
                if args.candidate_keyword_id
                else None,
                max_sites=args.max_sites,
                max_keywords=args.max_keywords,
            ).crawl()
        return 0

    if args.command == "report":
        with database.connect(args.db) as conn:
            output_dir = args.output_dir or Path("reports")
            print(generate_report(conn, args.date, output_dir))
        return 0

    if args.command == "crawl-and-report":
        app_config = load_app_config(args.app_config)
        if args.enable_playwright:
            object.__setattr__(app_config.playwright, "enabled", True)
        _override_concurrency(app_config, args)
        with database.connect(args.db) as conn:
            database.init_db(conn)
            Crawler(
                conn,
                app_config,
                site_ids=set(args.site_id) if args.site_id else None,
                candidate_keyword_ids=set(args.candidate_keyword_id)
                if args.candidate_keyword_id
                else None,
                max_sites=args.max_sites,
                max_keywords=args.max_keywords,
            ).crawl()
            print(generate_report(conn, args.date, Path(app_config.report.output_dir)))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
