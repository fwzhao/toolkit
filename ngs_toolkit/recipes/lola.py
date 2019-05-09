#!/usr/bin/env python

"""
A helper script to run Location Overlap Analysis (LOLA)
of a single region set in various sets of region-based annotations.
"""

import argparse
import os
import sys
from ngs_toolkit.general import lola


def parse_arguments():
    """
    Argument Parsing.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(dest="bed_file", help="BED file with query set regions.")
    parser.add_argument(
        dest="universe_file",
        help="BED file with universe where the query set came from.",
    )
    parser.add_argument(
        dest="output_folder", help="Output directory for produced files."
    )
    parser.add_argument(dest="genome", help="Genome assembly of the region set.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Don't overwrite any existing directory or file.",
    )
    parser.add_argument(
        "-c",
        "--cpus",
        dest="cpus",
        help="Number of CPUS/threads to use for analysis.",
        type=int,
    )
    args = parser.parse_args()

    return args


def main():
    print("LOLA analysis")
    args = parse_arguments()
    if os.path.exists(args.output_file) and (not args.overwrite):
        print("Output exists and `overwrite` is False, so not doing anything.")
        return 0

    print("Starting LOLA analysis.")

    lola(
        args.bed_file,
        args.universe_file,
        args.output_folder,
        args.genome,
        cpus=args.cpus,
    )

    print("Done.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Program canceled by user!")
        sys.exit(1)