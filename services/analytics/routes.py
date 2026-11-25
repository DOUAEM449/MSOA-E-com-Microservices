from fastapi import APIRouter, HTTPException, Query

import analytics_service
from consumer import request_replay

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
def analytics_summary():
    return analytics_service.get_summary()


@router.get("/events")
def analytics_events(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = None
):
    events = analytics_service.get_events(
        limit=limit,
        offset=offset,
        event_type=event_type
    )

    return {
        "count": len(events),
        "events": events
    }


@router.post("/replay")
def replay_events():
    if not request_replay():
        raise HTTPException(
            status_code=503,
            detail="Kafka consumer is not running"
        )

    return {
        "message": "Replay requested successfully",
        "topic": "ecommerce-events"
    }
