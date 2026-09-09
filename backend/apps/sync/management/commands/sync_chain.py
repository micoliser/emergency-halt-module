"""
Seed / refresh the indexer from studionet without Celery.

    python manage.py sync_chain --counts
    python manage.py sync_chain --all
    python manage.py sync_chain --protocol 0
"""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.sync import indexer
from apps.sync.genlayer_client import GenLayerError, get_reader


class Command(BaseCommand):
    help = "Read Halt Module views from GenLayer and upsert the local cache."

    def add_arguments(self, parser):
        parser.add_argument(
            "--protocol",
            type=int,
            default=None,
            help="Fast-path sync a single protocol id (plus its cases).",
        )
        parser.add_argument(
            "--case", type=int, default=None, help="Sync a single case id."
        )
        parser.add_argument(
            "--counts", action="store_true", help="Only read the count anchors."
        )
        parser.add_argument(
            "--all", action="store_true", help="Full poll-and-diff pass."
        )

    def handle(self, *args, **options):
        reader = get_reader()
        self.stdout.write(
            f"rpc={reader.rpc_url} contract={reader.contract_address or '(unset)'}"
        )
        try:
            if options["counts"]:
                result = indexer.sync_counts(reader=reader)
            elif options["protocol"] is not None:
                result = indexer.sync_protocol(
                    options["protocol"], reader=reader
                ).as_dict()
            elif options["case"] is not None:
                result = indexer.sync_case(options["case"], reader=reader).as_dict()
            elif options["all"]:
                result = indexer.poll_and_diff(reader=reader)
            else:
                raise CommandError(
                    "Pick one of --counts, --all, --protocol <id>, --case <id>."
                )
        except GenLayerError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(result, indent=2, default=str))
        self.stdout.write(self.style.SUCCESS("sync ok"))
