# Security Policy

The Atlas must be safe by default. Infrastructure data can create operational risk when it is too precise, too detailed, or combined with vulnerability context.

## Rules

- Do not store classified, restricted, or unlawfully obtained data.
- Do not map operational vulnerabilities.
- Do not publish sensitive facility coordinates at unnecessary precision.
- Prefer regional, city-level, or generalized geometries for sensitive infrastructure.
- Keep source licenses and usage constraints visible before ingestion.
- Treat API response size limits as a security and reliability control.

## Repository Controls

The repository blocks common heavy geospatial formats and local database files through `.gitignore` and `atlas.storage.validate_repo_file_safety`.
