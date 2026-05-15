from django.db.models import Avg, Count
from django.utils import timezone


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
