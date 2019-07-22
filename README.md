# player-tracker

A tool that automatically updates various TV trackers while you're watching stuff.

## Installation

Clone the repo, install dependencies.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python player-tracker.py
```

To enable services, uncomment lines in `services/__init__.py`.

## How it works
- Builds a list of files opened in your media player
- Filenames are parsed using [guessit](https://github.com/guessit-io/guessit)
- Titles are searched on various services
- Matching entries are updated
