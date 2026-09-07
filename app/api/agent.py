from fastapi import APIRouter

from app.models.search import AgentAnswer, AgentAskRequest

router = APIRouter(prefix="/v1/agent", tags=["agent"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("/query", response_model=AgentAnswer)
async def ask_scientist(body: AgentAskRequest) -> AgentAnswer:
    """
    Scientist Agent entry point.

    The implementation must call domain tools/services. Direct SQL, direct
    Elasticsearch queries, or direct Cypher from the LLM layer are forbidden.
    """
    _not_implemented()
