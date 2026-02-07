#!/usr/bin/env python
"""
AlphaGenome ISM Scanner for Galaxy

In-silico saturation mutagenesis — systematically mutates every position in a
region to all 3 alt bases and scores each. Uses score_ism_variants() with
server-side chunking and parallelism.
"""

import argparse
import csv
import logging
import sys

from alphagenome.data import genome
from alphagenome.models import dna_client
from alphagenome.models.variant_scorers import RECOMMENDED_VARIANT_SCORERS, tidy_scores

__version__ = "0.1.0"

ORGANISM_MAP = {
    "human": dna_client.Organism.HOMO_SAPIENS,
    "mouse": dna_client.Organism.MUS_MUSCULUS,
}

SEQUENCE_LENGTH_MAP = {
    "16KB": 16_384,
    "128KB": 131_072,
    "512KB": 524_288,
    "1MB": 1_048_576,
}


def create_model(api_key, local_model=False):
    if local_model:
        from alphagenome_research.model import dna_model
        return dna_model.create_from_huggingface("all_folds")
    return dna_client.create(api_key)


def parse_bed(bed_path, max_regions, max_region_width):
    """Parse BED file and return list of (chrom, start, end, name) tuples."""
    regions = []
    with open(bed_path) as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("track") or line.startswith("browser"):
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                logging.warning("Skipping malformed BED line %d: %s", line_num + 1, line)
                continue
            chrom = fields[0]
            start = int(fields[1])
            end = int(fields[2])
            name = fields[3] if len(fields) > 3 else f"{chrom}:{start}-{end}"
            width = end - start
            if width > max_region_width:
                logging.warning(
                    "Region %s is %dbp, exceeding max width %dbp — trimming to center %dbp",
                    name, width, max_region_width, max_region_width,
                )
                center = (start + end) // 2
                start = center - max_region_width // 2
                end = start + max_region_width
            if len(regions) >= max_regions:
                logging.warning("Reached max regions (%d), skipping remaining", max_regions)
                break
            regions.append((chrom, start, end, name))
    return regions


def run(args):
    logging.info("AlphaGenome ISM Scanner v%s", __version__)
    logging.info("Input: %s", args.input)
    logging.info("Scorers: %s", ", ".join(args.scorers))
    logging.info("Organism: %s", args.organism)
    logging.info("Sequence length: %s", args.sequence_length)
    logging.info("Max regions: %d, max region width: %dbp", args.max_regions, args.max_region_width)

    organism = ORGANISM_MAP[args.organism]
    seq_length = SEQUENCE_LENGTH_MAP[args.sequence_length]

    available_keys = list(RECOMMENDED_VARIANT_SCORERS.keys())
    for key in args.scorers:
        if key not in RECOMMENDED_VARIANT_SCORERS:
            logging.error("Unknown scorer key: %s (available: %s)", key, ", ".join(available_keys))
            sys.exit(1)
    selected_scorers = [RECOMMENDED_VARIANT_SCORERS[k] for k in args.scorers]

    regions = parse_bed(args.input, args.max_regions, args.max_region_width)
    if not regions:
        logging.error("No valid regions found in input BED file")
        sys.exit(1)
    logging.info("Loaded %d regions", len(regions))

    logging.info("Connecting to AlphaGenome...")
    model = create_model(args.api_key, local_model=args.local_model)
    logging.info("Model ready.")

    stats = {"regions": 0, "scored": 0, "errors": 0}
    all_rows = []

    for region_num, (chrom, start, end, name) in enumerate(regions):
        stats["regions"] += 1
        width = end - start
        logging.info("Region %d/%d: %s (%s:%d-%d, %dbp, %d mutations)",
                     region_num + 1, len(regions), name, chrom, start, end, width, width * 3)

        try:
            interval = genome.Interval(chrom, start, end).resize(seq_length)
            ism_interval = genome.Interval(chrom, start, end, strand="+")

            results = model.score_ism_variants(
                interval, ism_interval,
                variant_scorers=selected_scorers,
                organism=organism,
                max_workers=args.max_workers,
            )

            # results is list[list[AnnData]] — outer=variants, inner=scorers
            # Each variant is a single-base substitution at a position
            position = start
            alt_index = 0
            bases = ["A", "C", "G", "T"]

            for var_results in results:
                # Determine position and alt base from index
                # ISM generates 3 variants per position (all non-ref bases)
                ref_base_pos = start + (alt_index // 3)
                alt_base_idx = alt_index % 3

                df = tidy_scores(var_results)
                df.insert(0, "region", name)
                df.insert(1, "position", ref_base_pos)
                # We don't know the ref base without a reference genome, so
                # label by mutation index; the API returns them in order
                df.insert(2, "mutation_index", alt_base_idx)
                all_rows.append(df)
                alt_index += 1

            stats["scored"] += 1
            logging.info("Region %s: %d ISM results", name, len(results))

        except Exception as e:
            logging.error("Error scanning region %s (%s:%d-%d): %s", name, chrom, start, end, e)
            stats["errors"] += 1

    # Write output
    if all_rows:
        import pandas as pd
        combined = pd.concat(all_rows, ignore_index=True)
        combined.to_csv(args.output, sep="\t", index=False)
        logging.info("Wrote %d rows to %s", len(combined), args.output)
    else:
        with open(args.output, "w") as f:
            f.write("region\tposition\tmutation_index\n")
        logging.warning("No regions scored successfully")

    logging.info("=" * 50)
    logging.info("DONE — %d regions, %d scored, %d errors",
                 stats["regions"], stats["scored"], stats["errors"])

    if stats["errors"] > 0 and stats["scored"] == 0:
        logging.error("All regions failed. Check API key and network connectivity.")
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="In-silico saturation mutagenesis using AlphaGenome score_ism_variants()",
    )
    parser.add_argument("--input", required=True, help="Input BED file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    parser.add_argument("--api-key", required=True, help="AlphaGenome API key")
    parser.add_argument(
        "--organism", choices=["human", "mouse"], default="human",
    )
    parser.add_argument(
        "--scorers", nargs="+", default=["RNA_SEQ", "ATAC"],
        help="Scorer keys from RECOMMENDED_VARIANT_SCORERS",
    )
    parser.add_argument(
        "--sequence-length", choices=list(SEQUENCE_LENGTH_MAP.keys()), default="1MB",
    )
    parser.add_argument("--max-regions", type=int, default=10)
    parser.add_argument("--max-region-width", type=int, default=200)
    parser.add_argument("--max-workers", type=int, default=5)
    parser.add_argument("--local-model", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main():
    args = parse_arguments()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    try:
        run(args)
    except KeyboardInterrupt:
        logging.error("Interrupted")
        sys.exit(130)
    except Exception as e:
        logging.error("Fatal error: %s", e)
        if args.verbose:
            logging.exception("Details:")
        sys.exit(1)


if __name__ == "__main__":
    main()
