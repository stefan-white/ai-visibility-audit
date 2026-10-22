# Changelog

All notable changes are documented here. Format: Keep a Changelog; versioning: SemVer.

## [Unreleased]

### Added
- Fictional industrial equipment and SaaS prompt sets, each with five intent questions and one brand question.
- Standalone manual audit worksheet requiring no paid tools or API keys.
- Draft 2020-12 results schema and standard-library validation with field-specific errors.
- Security reporting guidance and sanitized bug, feature, and pull request templates.
- Offline fixture CI on pushes and pull requests for Python 3.10, 3.11, and 3.12.

### Fixed
- Invalid UTF-8 input now fails cleanly with exit code 2 before any report output.
- Standardized synthetic competitor placeholders to `.example` domains and corrected the example intent-answer denominator.

## [0.1.0] - 2026-10-22
### Added
- `SKILL.md`: provider-agnostic AI visibility & SEO audit procedure with budget
  controls, failure-vs-miss handling, and [Measured]/[Inferred] labelling.
- `scripts/scorecard.py`: renders a Markdown scorecard (and optional comparison
  with a previous run) from `results.json`; standard library only, with tests.
- Report template, example prompts, and a fully fictional "Acme Widgets" example.
