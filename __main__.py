"""Module entry point for ``python -m scraping_lab.perplexity_lab.perplexify``."""

try:
    from scraping_lab.perplexity_lab.perplexify.cli import main
except ModuleNotFoundError:
    from cli import main


if __name__ == "__main__":
    raise SystemExit(main())
