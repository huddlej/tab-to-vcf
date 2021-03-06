#!/bin/env python
"""
Convert the given tab-delimited document into a VCF 4.1 document for annotation with Seattle Seq.
"""
import argparse
import csv
from fastahack import FastaHack
import vcf
from vcf.model import _Record


TEMPLATE_VCF_FILE = "template-4.1.vcf"
VCF_TO_FIELDS = (
    ("#CHROM", "Chrom"),
    ("POS", "Pos(hg19)"),
    ("ID", "Unique id"),
    ("REF", "Ref"),
    ("ALT", "Allele"),
    ("QUAL", "QUAL"),
    ("FILTER", "FILTER")
)
CHROMOSOME_INDEX=0
POSITION_INDEX=1
REF_INDEX=3
ALT_INDEX=4


def get_sequence(reference_dict, chrom, position):
    position = int(position)
    return reference_dict["%s:%s-%s" % (chrom, position, position)].upper()


def gatk_indel_to_vcf(vcf_row, reference_dict):
    """
    Convert the given indel from GATK format to VCF 4.1 standard. For example,
    the following lines should be converted from:

    2       60689253        1720    *       +G      .       .       .       .
    21      38877833        1721    *       -C      .       .       .       .
    21      47958429        1722    *       +CTGGTCT        .       .       .       .

    to:

    2       60689253        1720    A       AG      .       .       .       .
    21      38877833        1721    GC      G       .       .       .       .
    21      47958429        1722    A       ACTGGTCT        .       .       .       .

    >>> reference_dict = FastaHack("human_1kg_v37.fasta")
    >>> gatk_indel_to_vcf(['2', 60689253, '1720', '*', '+G', '.', '.', '.', '.'], reference_dict)
    ['2', 60689253, '1720', 'A', 'AG', '.', '.', '.', '.']
    >>> gatk_indel_to_vcf(['21', 38877833, '1721', '*', '-C', '.', '.', '.', '.'], reference_dict)
    ['21', 38877833, '1721', 'GC', 'G', '.', '.', '.', '.']
    >>> gatk_indel_to_vcf(['21', 47958429, '1722', '*', '+CTGGTCT', '.', '.', '.', '.'], reference_dict)
    ['21', 47958429, '1722', 'A', 'ACTGGTCT', '.', '.', '.', '.']
    """
    # Load the base at the given position.
    reference_base = get_sequence(reference_dict, vcf_row[CHROMOSOME_INDEX], vcf_row[POSITION_INDEX])

    # Create a new reference allele based on the event type (the position's base
    # for insertions, the position base plus the deleted base(s) for deletions).

    # Create a new alternate allele based on the event type (the position's base
    # plus the inserted base(s) for insertions, the position's base for
    # deletions).
    if vcf_row[ALT_INDEX].startswith("+"):
        vcf_row[REF_INDEX] = reference_base
        vcf_row[ALT_INDEX] = vcf_row[ALT_INDEX].replace("+", reference_base)
    elif vcf_row[ALT_INDEX].startswith("-"):
        vcf_row[REF_INDEX] = "%s%s" % (reference_base, vcf_row[ALT_INDEX].lstrip("-"))
        vcf_row[ALT_INDEX] = reference_base

    return vcf_row


def tab_to_vcf(input_file, output_file, reference_file):
    """
    Convert tab-delimited file to VCF.

    Support for the fixed VCF fields: #CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO

    PyVCF's _Record class requires the following arguments:

    CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, FORMAT, sample_indexes
    """
    reference_dict = FastaHack(reference_file)

    with open(input_file, "r") as input_fh:
        reader = csv.DictReader(input_fh, delimiter="\t")

        with open(TEMPLATE_VCF_FILE, "r") as template_fh:
            vcf_reader = vcf.Reader(template_fh)

            with open(output_file, "w") as output_fh:
                vcf_writer = vcf.Writer(output_fh, vcf_reader, lineterminator='\n')

                for row in reader:
                    args = [row.get(tab_field, ".")
                            for vcf_field, tab_field in VCF_TO_FIELDS]

                    # Convert position to an integer.
                    args[POSITION_INDEX] = int(args[POSITION_INDEX])

                    # Convert indels from GATK to VCF format.
                    if args[ALT_INDEX].startswith(("+", "-")) and not "/" in args[ALT_INDEX]:
                        args = gatk_indel_to_vcf(args, reference_dict)

                    # Convert alternate allele scalar to a list.
                    args[ALT_INDEX] = [args[ALT_INDEX]]

                    # Add empty entries for INFO, FORMAT, and sample_indexes.
                    args.extend([{}, ".", []])

                    record = _Record(*args)
                    vcf_writer.write_record(record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="tab-delimited input")
    parser.add_argument("output_file", help="VCF 4.1 output")
    parser.add_argument("reference_file", help="reference assembly for variants in a single FASTA file")
    args = parser.parse_args()

    tab_to_vcf(args.input_file, args.output_file, args.reference_file)
