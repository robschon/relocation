# Relocation CLI Reference

This document lists everything currently supported by the `relocation` command line interface.

## Global command

```bash
relocation [OPTIONS] COMMAND [ARGS]...
```

Global options:
- `--install-completion`
- `--show-completion`
- `--help`

Top-level commands:
- `init`
- `location`
- `category`
- `score`
- `weight`
- `research`
- `pros-cons`
- `visa`
- `profile`
- `rank`

## Command groups

### `relocation init`

Initialize the database and seed default data.

```bash
relocation init
```

### `relocation location`

Manage locations.

```bash
relocation location list
relocation location add NAME COUNTRY [--region TEXT] [--population INTEGER] [--desc TEXT]
relocation location show QUERY
relocation location remove QUERY [--yes|-y]
```

Notes:
- `QUERY` accepts either location ID or case-insensitive name substring.
- `remove` deletes the location and related records.

### `relocation category`

List categories.

```bash
relocation category list
```

### `relocation score`

Manage location scores.

```bash
relocation score set LOCATION CATEGORY SCORE [--notes TEXT]
relocation score list [--location|-l TEXT] [--category|-c TEXT]
relocation score matrix
```

Notes:
- `LOCATION` and `CATEGORY` accept ID or case-insensitive substring.
- `SCORE` must be in `0..10`.
- `set` is upsert behavior (create or update existing score).

### `relocation weight`

Manage per-user category weights.

```bash
relocation weight set USER_NAME CATEGORY WEIGHT
relocation weight list [--user|-u TEXT]
relocation weight matrix
```

Notes:
- Valid users are `husband` and `wife`.
- `CATEGORY` accepts ID or case-insensitive substring.
- `WEIGHT` must be in `0..10`.
- `set` is upsert behavior (create or update existing weight).

### `relocation research`

Manage research entries.

```bash
relocation research add LOCATION --content TEXT [--category|-c TEXT] [--source|-s TEXT]
relocation research list [--location|-l TEXT] [--category|-c TEXT]
relocation research show ID
relocation research remove ID
```

Notes:
- `LOCATION` and optional `--category` accept ID or case-insensitive substring.
- `--content` is required on `add`.

### `relocation pros-cons`

Manage pros and cons.

```bash
relocation pros-cons add-pro LOCATION CONTENT [--category|-c TEXT]
relocation pros-cons add-con LOCATION CONTENT [--category|-c TEXT]
relocation pros-cons list [--location|-l TEXT]
relocation pros-cons remove ID
```

Notes:
- `LOCATION` and optional `--category` accept ID or case-insensitive substring.

### `relocation visa`

Manage visa/immigration entries.

```bash
relocation visa add COUNTRY VISA_TYPE [--desc TEXT] [--requirements|-r TEXT] [--pathway TEXT] [--timeline|-t TEXT] [--cost TEXT] [--notes|-n TEXT]
relocation visa list [--country|-c TEXT]
relocation visa show ID
```

### `relocation profile`

Manage relocation profile responses.

```bash
relocation profile build
relocation profile show
relocation profile export [--output|-o TEXT]
```

### `relocation rank`

Show weighted rankings.

```bash
relocation rank [--user|-u TEXT] [--detailed|-d]
```

Options:
- `--user`: `husband`, `wife`, or `combined` (default)
- `--detailed`: include per-category breakdown

## Shared matching behavior

For commands that accept location/category by text:
- Numeric input is treated as an ID first.
- Otherwise, case-insensitive substring matching is used.
- If zero matches are found, the command exits with an error.
- If multiple matches are found, the command exits as ambiguous and lists candidates.

