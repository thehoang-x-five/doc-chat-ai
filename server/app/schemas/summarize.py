"""
Schemas for Smart Summarization with Role/Format Options.
Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6, 23.7, 23.8
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SummaryAudience(str, Enum):
    """Target audience for the summary."""
    EXECUTIVE = "executive"      # Focus on key decisions, metrics, action items
    TECHNICAL = "technical"      # Include technical details, specs, implementation
    LEGAL = "legal"              # Highlight obligations, risks, compliance
    GENERAL = "general"          # General audience, balanced content


class SummaryFormat(str, Enum):
    """Output format for the summary."""
    PARAGRAPH = "paragraph"      # Flowing prose paragraphs
    BULLET = "bullet"            # Bullet point list
    TABLE = "table"              # Structured table format
    TIMELINE = "timeline"        # Chronological timeline
    CHECKLIST = "checklist"      # Actionable checklist


class SummaryCitation(BaseModel):
    """Citation linking summary content to source document."""
    document_id: str
    document_title: Optional[str] = None
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None
    section: Optional[str] = None
    text_excerpt: str = Field(..., description="Relevant text from source")
    relevance_score: float = Field(ge=0.0, le=1.0)


class SummarizeRequest(BaseModel):
    """Request to generate a summary."""
    document_ids: List[str] = Field(..., min_length=1, description="Documents to summarize")
    audience: SummaryAudience = Field(default=SummaryAudience.GENERAL)
    format: SummaryFormat = Field(default=SummaryFormat.PARAGRAPH)
    max_length: Optional[int] = Field(default=500, ge=50, le=5000, description="Max words")
    focus_topics: Optional[List[str]] = Field(default=None, description="Topics to focus on")
    language: str = Field(default="en", description="Output language code")
    include_citations: bool = Field(default=True)


class SummaryResult(BaseModel):
    """Result of a summarization request."""
    id: str
    workspace_id: str
    document_ids: List[str]
    document_titles: List[str] = []
    audience: SummaryAudience
    format: SummaryFormat
    language: str
    content: str = Field(..., description="The generated summary")
    citations: List[SummaryCitation] = []
    word_count: int = 0
    focus_topics: Optional[List[str]] = None
    created_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


class SummaryListResponse(BaseModel):
    """Response for listing summaries."""
    summaries: List[SummaryResult]
    total: int
    skip: int
    limit: int


# Audience-specific prompt templates
AUDIENCE_PROMPTS = {
    SummaryAudience.EXECUTIVE: """
You are summarizing for EXECUTIVE leadership. Focus on:
- Key decisions and strategic implications
- Important metrics, KPIs, and financial data
- Action items and next steps
- Risks and opportunities
- Bottom-line impact

Keep the language concise and business-focused. Avoid technical jargon.
""",
    SummaryAudience.TECHNICAL: """
You are summarizing for a TECHNICAL audience. Include:
- Technical specifications and requirements
- Implementation details and architecture
- APIs, data formats, and integrations
- Performance metrics and benchmarks
- Technical dependencies and constraints

Use appropriate technical terminology. Be precise and detailed.
""",
    SummaryAudience.LEGAL: """
You are summarizing for a LEGAL audience. Highlight:
- Contractual obligations and commitments
- Legal risks and liabilities
- Compliance requirements and regulations
- Terms, conditions, and warranties
- Intellectual property considerations
- Dispute resolution and governing law

Use precise legal language. Flag any ambiguous terms.
""",
    SummaryAudience.GENERAL: """
You are summarizing for a GENERAL audience. Provide:
- Clear overview of main topics
- Key points and takeaways
- Important facts and figures
- Balanced coverage of all sections

Use clear, accessible language. Avoid jargon.
""",
}


# Format-specific output instructions
FORMAT_INSTRUCTIONS = {
    SummaryFormat.PARAGRAPH: """
Output as flowing prose paragraphs. Use clear topic sentences.
Organize logically with smooth transitions between ideas.
""",
    SummaryFormat.BULLET: """
Output as a bullet point list:
• Main point 1
• Main point 2
  - Sub-point if needed
• Main point 3

Keep each bullet concise and self-contained.
""",
    SummaryFormat.TABLE: """
Output as a structured table in markdown format:

| Category | Key Points | Details |
|----------|------------|---------|
| Topic 1  | Summary    | More info |
| Topic 2  | Summary    | More info |

Organize information into logical categories.
""",
    SummaryFormat.TIMELINE: """
Output as a chronological timeline:

**[Date/Phase 1]**: Event or milestone description
**[Date/Phase 2]**: Event or milestone description
**[Date/Phase 3]**: Event or milestone description

Order events chronologically. Include dates when available.
""",
    SummaryFormat.CHECKLIST: """
Output as an actionable checklist:

- [ ] Action item 1
- [ ] Action item 2
- [x] Completed item (if applicable)
- [ ] Action item 3

Focus on actionable items and tasks.
""",
}
