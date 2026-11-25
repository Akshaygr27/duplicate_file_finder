import csv
import hashlib
from pathlib import Path
import re


def format_size(num_bytes: int) -> str:
    """Format byte counts cleanly (e.g., 2.5 MB)."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}".rstrip("0").rstrip(".")
        size /= 1024
    return f"{num_bytes} B"


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Read a file in binary chunks and return its SHA-256 hex digest."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_duplicate_groups(root_dir: Path) -> tuple[list[dict], int]:
    """
    Recursively scan root_dir and return:
      - list of duplicate group dicts (each with 'hash', 'size_bytes', 'files', 'wasted_bytes')
      - total wasted bytes across all duplicate groups
    """
    size_groups: dict[int, list[Path]] = {}
    scanned_files = 0

    for path in root_dir.rglob("*"):
        try:
            if not path.is_file() or path.is_symlink():
                continue
            size = path.stat().st_size
            if size == 0:
                # Skip empty 0-byte files unless needed; change to keep if desired
                continue
            size_groups.setdefault(size, []).append(path.resolve())
            scanned_files += 1
        except (PermissionError, OSError) as exc:
            print(f"Warning: Skipped '{path}': {exc}")

    # Only hash files that share the exact same byte size with at least one other file
    hash_groups: dict[str, list[Path]] = {}
    size_by_hash: dict[str, int] = {}

    for size, paths in size_groups.items():
        if len(paths) < 2:
            continue
        for file_path in paths:
            try:
                file_hash = compute_sha256(file_path)
                hash_groups.setdefault(file_hash, []).append(file_path)
                size_by_hash[file_hash] = size
            except (PermissionError, OSError) as exc:
                print(f"Warning: Could not hash '{file_path}': {exc}")

    duplicate_groups: list[dict] = []
    total_wasted_bytes = 0

    for file_hash, files in hash_groups.items():
        if len(files) < 2:
            continue
        files_sorted = sorted(files, key=lambda p: str(p).lower())
        size_bytes = size_by_hash[file_hash]
        duplicate_count = len(files_sorted) - 1
        wasted_bytes = size_bytes * duplicate_count
        total_wasted_bytes += wasted_bytes

        duplicate_groups.append(
            {
                "hash": file_hash,
                "size_bytes": size_bytes,
                "files": files_sorted,
                "duplicate_copies": duplicate_count,
                "wasted_bytes": wasted_bytes,
            }
        )

    # Sort largest space savings first
    duplicate_groups.sort(key=lambda g: g["wasted_bytes"], reverse=True)
    print(f"\nScanned {scanned_files} non-empty file(s) across '{root_dir}'.")
    return duplicate_groups, total_wasted_bytes


def display_duplicate_report(groups: list[dict], total_wasted_bytes: int, root_dir: Path) -> None:
    """Print grouped duplicate files, sizes, copy counts, and storage savings."""
    if not groups:
        print("No duplicate files found.")
        return

    for idx, group in enumerate(groups, start=1):
        print(f"\nDuplicate Group {idx}:")
        for file_path in group["files"]:
            try:
                rel_display = file_path.relative_to(root_dir.resolve())
            except ValueError:
                rel_display = file_path
            print(f"  {rel_display}")
        print(f"  File Size: {format_size(group['size_bytes'])}")
        print(f"  Duplicate Copies: {group['duplicate_copies']}")
        print(f"  Potential Space Savings: {format_size(group['wasted_bytes'])}")

    print("\n" + "=" * 42)
    print(f"Total Duplicate Groups         : {len(groups)}")
    print(f"Total Storage Occupied by Dupes: {format_size(total_wasted_bytes)}")
    print("=" * 42)


def export_report_to_csv(groups: list[dict], csv_path: Path, root_dir: Path) -> None:
    """Export all duplicate group entries into a CSV report."""
    fieldnames = [
        "Group",
        "Role",
        "Relative Path",
        "Full Path",
        "SHA256 Hash",
        "File Size (Bytes)",
        "File Size",
        "Duplicate Copies in Group",
        "Group Potential Space Savings (Bytes)",
        "Group Potential Space Savings",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for group_num, group in enumerate(groups, start=1):
            for file_idx, file_path in enumerate(group["files"]):
                try:
                    rel_path = str(file_path.relative_to(root_dir.resolve()))
                except ValueError:
                    rel_path = str(file_path)

                writer.writerow(
                    {
                        "Group": group_num,
                        "Role": "Original (Keep candidate)" if file_idx == 0 else "Duplicate copy",
                        "Relative Path": rel_path,
                        "Full Path": str(file_path),
                        "SHA256 Hash": group["hash"],
                        "File Size (Bytes)": group["size_bytes"],
                        "File Size": format_size(group["size_bytes"]),
                        "Duplicate Copies in Group": group["duplicate_copies"],
                        "Group Potential Space Savings (Bytes)": group["wasted_bytes"],
                        "Group Potential Space Savings": format_size(group["wasted_bytes"]),
                    }
                )

    print(f"CSV report exported to: {csv_path}")


def parse_selection_indices(raw_input: str, max_index: int) -> list[int]:
    """Parse comma-separated numbers or ranges (e.g. '2, 4-5') into 1-based indices."""
    selected: set[int] = set()
    tokens = [t.strip() for t in raw_input.split(",") if t.strip()]
    for token in tokens:
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start <= end:
                for num in range(start, end + 1):
                    if 1 <= num <= max_index:
                        selected.add(num)
        elif token.isdigit():
            num = int(token)
            if 1 <= num <= max_index:
                selected.add(num)
    return sorted(selected)


def interactive_delete_duplicates(groups: list[dict], root_dir: Path) -> None:
    """Allow the user to explicitly pick which duplicate files to remove."""
    choice = input("\nWould you like to select specific duplicate files to remove? (y/n): ").strip().lower()
    if choice != "y":
        print("No files were deleted.")
        return

    indexed_files: list[tuple[int, Path]] = []
    print("\n--- Selectable Files (Item #1 in each group is listed first as a keep reference) ---")
    item_num = 1
    for group_idx, group in enumerate(groups, start=1):
        print(f"Group {group_idx} ({format_size(group['size_bytes'])} each):")
        for f_idx, file_path in enumerate(group["files"]):
            try:
                rel_display = file_path.relative_to(root_dir.resolve())
            except ValueError:
                rel_display = file_path
            tag = "[First/Keep]" if f_idx == 0 else "[Duplicate]"
            print(f"  [{item_num}] {tag} {rel_display}")
            indexed_files.append((group_idx, file_path))
            item_num += 1

    raw_selection = input(
        "\nEnter item numbers or ranges to delete (e.g. 2, 5, 7-8) or press Enter to cancel: "
    ).strip()
    if not raw_selection:
        print("Deletion cancelled. No files were removed.")
        return

    selected_nums = parse_selection_indices(raw_selection, len(indexed_files))
    if not selected_nums:
        print("No valid item numbers selected. No files were removed.")
        return

    targets = [indexed_files[n - 1][1] for n in selected_nums]
    print("\nYou selected the following file(s) for PERMANENT deletion:")
    for target in targets:
        print(f"  - {target}")

    confirm = input("Type DELETE to confirm permanent removal: ").strip()
    if confirm != "DELETE":
        print("Confirmation did not match 'DELETE'. No files were removed.")
        return

    deleted_count = 0
    reclaimed_bytes = 0
    for target in targets:
        try:
            size = target.stat().st_size
            target.unlink()
            deleted_count += 1
            reclaimed_bytes += size
            print(f"Deleted: {target}")
        except (PermissionError, OSError) as exc:
            print(f"Failed to delete '{target}': {exc}")

    print(f"\nRemoved {deleted_count} file(s). Space reclaimed: {format_size(reclaimed_bytes)}.")


def main() -> None:
    folder_input = input("Enter folder path to scan for duplicates: ").strip().strip('"').strip("'")
    root_dir = Path(folder_input).expanduser()

    if not root_dir.exists() or not root_dir.is_dir():
        print(f"Error: '{root_dir}' is not a valid folder.")
        return

    groups, total_wasted_bytes = find_duplicate_groups(root_dir)
    display_duplicate_report(groups, total_wasted_bytes, root_dir)

    if not groups:
        return

    export_choice = input("\nExport duplicate report to CSV? (y/n): ").strip().lower()
    if export_choice == "y":
        default_csv = root_dir / "duplicate_files_report.csv"
        custom_name = input(f"Enter CSV path (press Enter for '{default_csv}'): ").strip().strip('"').strip("'")
        csv_target = Path(custom_name).expanduser() if custom_name else default_csv
        if not csv_target.parent.exists():
            csv_target.parent.mkdir(parents=True, exist_ok=True)
        export_report_to_csv(groups, csv_target, root_dir)

    interactive_delete_duplicates(groups, root_dir)


if __name__ == "__main__":
    main()