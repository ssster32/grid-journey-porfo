from django.core.management.base import BaseCommand, CommandError

from maps.models import MapArea
from maps.services import (
    run_grid_generation_for_area,
    truncate_grid_generation_error_message,
)


class Command(BaseCommand):
    help = "Process pending MapAreas and generate GridCells synchronously."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of pending MapAreas to process.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show pending MapAreas without processing them.",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")
        dry_run = options.get("dry_run")

        if limit is not None and limit <= 0:
            raise CommandError("--limit は 1 以上の整数で指定してください。")

        pending_areas = MapArea.objects.filter(
            grid_generation_status=MapArea.GridGenerationStatus.PENDING,
        ).order_by("created_at", "id")
        if limit is not None:
            pending_areas = pending_areas[:limit]

        pending_areas = list(pending_areas)
        self.stdout.write(f"Found {len(pending_areas)} pending MapArea(s).")

        if dry_run:
            self.stdout.write("Dry run: no changes will be made.")
            for area in pending_areas:
                self.stdout.write(
                    f'Target MapArea id={area.id} name="{area.name}"'
                )
            return

        processed = 0
        completed = 0
        fallback_completed = 0
        failed = 0

        for area in pending_areas:
            processed += 1
            self.stdout.write(f'Processing MapArea id={area.id} name="{area.name}"')
            try:
                grid_cells = run_grid_generation_for_area(area)
            except Exception as error:
                area.refresh_from_db()
                failed += 1
                error_message = truncate_grid_generation_error_message(error, 200)
                self.stdout.write(
                    f'Failed MapArea id={area.id} '
                    f"status={area.grid_generation_status} error=\"{error_message}\""
                )
                continue

            area.refresh_from_db()
            if area.grid_generation_status == MapArea.GridGenerationStatus.COMPLETED:
                completed += 1
            elif (
                area.grid_generation_status
                == MapArea.GridGenerationStatus.FALLBACK_COMPLETED
            ):
                fallback_completed += 1

            self.stdout.write(
                f"Completed MapArea id={area.id} "
                f"status={area.grid_generation_status} cells={len(grid_cells)}"
            )

        self.stdout.write(
            "Done. "
            f"processed={processed} "
            f"completed={completed} "
            f"fallback_completed={fallback_completed} "
            f"failed={failed}"
        )
