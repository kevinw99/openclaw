"""Turn data model - one user prompt + AI response exchange"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Turn:
    """One conversation turn: user prompt -> AI response."""
    turn_number: int
    timestamp: str
    title: str
    user_prompt: str
    assistant_response: str
    tool_counts: Dict[str, int] = field(default_factory=dict)
    tool_narrative: str = ""
    is_long_prompt: bool = False

    @property
    def tool_summary_line(self) -> str:
        """Generate tool summary line, e.g. 'Read (4), Write (5), Bash (1)'."""
        if not self.tool_counts:
            return ""
        parts = [f"{name} ({count})" for name, count in sorted(self.tool_counts.items())]
        return ", ".join(parts)

    @property
    def time_short(self) -> str:
        """Extract HH:MM format time."""
        if len(self.timestamp) >= 16:
            return self.timestamp[11:16]
        return self.timestamp
