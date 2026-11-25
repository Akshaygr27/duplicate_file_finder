# Duplicate File Finder

A Python utility that recursively scans folders and subfolders to detect files with identical content using SHA-256 hashing—even when renamed—calculates wasted storage space, exports a CSV report, and optionally lets you remove selected duplicate files safely.

## Features

- **Recursive Content Hashing:** Traverses all subdirectories, pre-groups files by byte size, and computes chunked SHA-256 hashes to find true duplicates regardless of filename or folder location.
- **Storage & Savings Breakdown:** Displays file paths, file sizes, duplicate copy counts, potential space savings per group, and total wasted storage.
- **Optional CSV Export:** Exports duplicate group details, paths, sizes, and hashes to a CSV report (`duplicate_files_report.csv` or a custom path).
- **Safe, Manual Deletion:** Never deletes files automatically; lets you opt in, pick specific item numbers or ranges, and type `DELETE` to confirm permanent removal.

## Tech Stack

- **Python 3** (standard library only: `pathlib`, `hashlib`, `csv`, `re`)

## Getting Started

### Prerequisites

- Python 3.9 or higher installed on your system. No external packages required.

### Installation & Usage

1. Clone or download the repository and open a terminal in the project folder:

   ```bash
   git clone <your-repo-url>
   cd <your-repo-folder>

2. Run:

    python duplicate_file_finder.py