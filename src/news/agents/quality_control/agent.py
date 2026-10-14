import logging
from typing import Tuple, List
from ..base import NewsStory, AgentPhase
from .validator import QCValidator

logger = logging.getLogger(__name__)


class QualityControlAgent:
    """Agent 6 — Quality Control Agent
    - Checks audio/video synchronization.
    - Verifies image presence and script duration.
    - Confirms video rendering integrity and file size.
    - Reports quality status and editorial notes back to Orchestrator.
    """

    def __init__(self):
        self.validator = QCValidator()

    async def audit_story(self, story: NewsStory) -> Tuple[bool, List[str]]:
        logger.info(f"QualityControlAgent: Auditing media package for '{story.title}'...")
        passed, notes = await self.validator.validate_story(story)

        story.media.qc_passed = passed
        story.media.qc_notes = notes

        if passed:
            story.status = AgentPhase.COMPLETED
            story.progress_pct = 100
            story.status_message = "QC Audit Passed • Ready for Broadcast"
            logger.info(f"QualityControlAgent: PASSED audit for story {story.id}")
        else:
            story.status = AgentPhase.FAILED
            story.status_message = f"QC Failed: {'; '.join(notes)}"
            logger.warning(f"QualityControlAgent: FAILED audit for story {story.id}: {notes}")

        return passed, notes
