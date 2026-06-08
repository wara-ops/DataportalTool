"""Table-rendering helpers for the dataportal CLI output.

These functions print the fixed-width tables shown by the ``WCIBConnection``
list/create operations. They are kept separate from the HTTP client so the
presentation logic does not bloat ``upload.py``. Output is intentionally
byte-for-byte identical to the original inline formatting.
"""


def print_created_dataset(j: dict) -> None:
    """Print the one-row table describing a freshly-created dataset."""
    fmt = "{:>9} | {:<40}"
    print(fmt.format("DatasetID", "ContainerName"))
    print("-" * 10 + "+" + "-" * 98)
    print(fmt.format(j.get("DatasetID", "-"), j.get("ContainerName", "-")))


def print_datasets(datasets: list) -> None:
    """Print the table listing the user's datasets."""
    fmt = "{:>9} | {:>40} | {:>30} | {:>10} | {:>10}"
    print(
        fmt.format("DatasetID", "DatasetName", "CreateDate", "Category", "Organization")
    )
    print("+".join("-" * n for n in (10, 42, 32, 12, 15)))
    for entry in datasets:
        print(
            fmt.format(
                entry["DatasetID"],
                entry["DatasetName"],
                entry["CreateDate"],
                entry["Category"],
                entry["Organization"],
            )
        )


def print_files(file_groups: list) -> None:
    """Print the table listing files (data + extra) in a dataset.

    ``file_groups`` is an iterable of lists of file entry dicts; each group is
    printed followed by a separator, and a final total row is appended.
    """
    num_files = 0
    total_size = 0
    fmt = "{:>6} | {:>30} | {:>30} | {:>10} | {:>12} | {}"
    separator = "+".join("-" * n for n in (7, 32, 32, 12, 14, 23))
    print(
        fmt.format(
            "FileID", "StartDate", "StopDate", "Entries", "FileSize", "MFileName"
        )
    )
    print(separator)

    for files in file_groups:
        if not isinstance(files, list):
            continue

        group_count = 0

        for entry in files:
            print(
                fmt.format(
                    entry["FileID"] or "n/a",
                    entry["StartDate"] or "n/a",
                    entry["StopDate"] or "n/a",
                    entry["MetricEntries"] or "n/a",
                    entry["FileSize"] or "n/a",
                    entry["MFileName"],
                )
            )

            group_count += 1
            total_size += entry["FileSize"]

        if group_count > 0:
            print(separator)

        num_files += group_count

    if num_files > 0:
        print(fmt.format(num_files, "", "", "", total_size, ""))
