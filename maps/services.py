from math import ceil

from django.db.models import Avg, Count
from django.utils import timezone

from .models import GridCell


METERS_PER_DEGREE = 111000


def generate_grid_cells_for_area(map_area):
    """Generate and save GridCell rows for one MapArea."""
    if map_area.grid_size_meters <= 0:
        raise ValueError("grid_size_meters は 0 より大きい値にしてください。")
    if map_area.north <= map_area.south:
        raise ValueError("north は south より大きい値にしてください。")
    if map_area.east <= map_area.west:
        raise ValueError("east は west より大きい値にしてください。")
    if map_area.grid_cells.exists():
        raise ValueError("この MapArea には既に GridCell があります。")

    lat_step = map_area.grid_size_meters / METERS_PER_DEGREE
    lng_step = map_area.grid_size_meters / METERS_PER_DEGREE
    row_count = ceil((map_area.north - map_area.south) / lat_step)
    col_count = ceil((map_area.east - map_area.west) / lng_step)

    grid_cells = []
    for row_index in range(row_count):
        cell_north = map_area.north - row_index * lat_step
        cell_south = max(map_area.south, cell_north - lat_step)

        for col_index in range(col_count):
            cell_west = map_area.west + col_index * lng_step
            cell_east = min(map_area.east, cell_west + lng_step)

            grid_cells.append(
                GridCell(
                    area=map_area,
                    row_index=row_index,
                    col_index=col_index,
                    north=cell_north,
                    south=cell_south,
                    east=cell_east,
                    west=cell_west,
                    initial_score=0,
                    average_user_score=0,
                    rating_count=0,
                    calculated_score=0,
                    score_updated_at=None,
                )
            )

    return GridCell.objects.bulk_create(grid_cells)


def update_grid_cell_score(grid_cell):
    """Recalculate and save score fields for one GridCell."""
    rating_summary = grid_cell.ratings.aggregate(
        average_score=Avg("score"),
        rating_count=Count("id"),
    )
    rating_count = rating_summary["rating_count"]

    if rating_count == 0:
        grid_cell.average_user_score = 0
        grid_cell.rating_count = 0
        grid_cell.calculated_score = grid_cell.initial_score
        grid_cell.score_updated_at = None
    else:
        average_user_score = rating_summary["average_score"]
        grid_cell.average_user_score = average_user_score
        grid_cell.rating_count = rating_count
        grid_cell.calculated_score = (
            grid_cell.initial_score + average_user_score
        ) / 2
        grid_cell.score_updated_at = timezone.now()

    grid_cell.save(
        update_fields=[
            "average_user_score",
            "rating_count",
            "calculated_score",
            "score_updated_at",
            "updated_at",
        ]
    )

    return grid_cell
