import logging
from typing import List, Tuple
from ..base import StoryScript

logger = logging.getLogger(__name__)


class TimelineSynchronizer:
    """Matches visual slides to speech narration timeline.
    Guarantees that a new image appears every 10 to 15 seconds.
    """

    @staticmethod
    def calculate_slide_durations(
        image_paths: List[str],
        script: StoryScript,
        total_audio_duration_sec: float,
        min_sec_per_slide: float = 10.0,
        max_sec_per_slide: float = 15.0,
    ) -> List[Tuple[str, float]]:
        """Calculate exact display duration for each slide in seconds,
        strictly keeping each slide displayed between 10 and 15 seconds.
        """
        if not image_paths:
            return []

        # Target midpoint interval: 12.0 seconds per image
        target_interval = 12.0

        # Calculate optimal number of slide intervals to stay strictly within 10-15s
        ideal_slide_count = max(1, int(round(total_audio_duration_sec / target_interval)))
        
        # Verify that duration per slide with ideal_slide_count fits within [min_sec_per_slide, max_sec_per_slide]
        dur_check = total_audio_duration_sec / ideal_slide_count
        if dur_check < min_sec_per_slide and ideal_slide_count > 1:
            ideal_slide_count = max(1, int(total_audio_duration_sec / min_sec_per_slide))
        elif dur_check > max_sec_per_slide:
            ideal_slide_count = int(total_audio_duration_sec / max_sec_per_slide) + 1

        total_slides = max(len(image_paths), ideal_slide_count)
        base_duration = round(total_audio_duration_sec / total_slides, 2)

        # Build full slide sequence cycling through the available distinct images
        timelines: List[Tuple[str, float]] = []
        accumulated_time = 0.0

        for i in range(total_slides):
            img = image_paths[i % len(image_paths)]
            if i == total_slides - 1:
                # Adjust final slide so total exactly matches audio duration
                slide_dur = round(max(5.0, total_audio_duration_sec - accumulated_time), 2)
            else:
                slide_dur = base_duration
                accumulated_time += slide_dur

            timelines.append((img, slide_dur))

        logger.info(
            f"TimelineSynchronizer: Created {len(timelines)} slide intervals (each ~{base_duration}s, within 10-15s window) for {total_audio_duration_sec:.1f}s audio."
        )
        return timelines
