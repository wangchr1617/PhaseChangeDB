from fastapi import APIRouter

from app.models.search import SearchRequest, SearchResponse

router = APIRouter(prefix="/v1/search", tags=["search"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("", response_model=SearchResponse)
async def search(body: SearchRequest) -> SearchResponse:
    """Search service: Elasticsearch lexical / semantic / RRF-hybrid retrieval."""
    _not_implemented()
