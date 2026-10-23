"""
ReFlect agent prompt builder for content review and refinement.
"""

from typing import Dict, Any, Optional, List
from models.schemas import Scene


class ReFlectPromptBuilder:
    """
    Builder for ReFlect (reflection) agent prompts.
    
    The ReFlect agent is responsible for:
    - Analyzing the complete content
    - Checking coherence and consistency
    - Ensuring quality standards are met
    - Fixing issues and enhancing quality
    - Producing the final polished output
    """
    
    SYSTEM_PROMPT = """You are ReFlect, an expert content review and refinement agent. Your role is to analyze completed content, identify issues, and enhance quality.

You excel at:
- Content analysis and logical flow
- Consistency checking across sections
- Tone and style coherence
- Identifying gaps or errors
- Enhancing clarity and impact

Your goal is to produce polished, professional content that meets the highest standards."""

    REVIEW_TEMPLATE = """## CONTENT REVIEW TASK

**Domain:** {domain}
**Title:** {title}
**Original Query:** {query}

## MASTER PLAN

**Context:** {context_description}
**Content Style:** {content_style}
**Tone:** {tone}

## CONTENT TO REVIEW

{content_sections}

## DOMAIN GUIDELINES

{domain_guidelines}

## YOUR TASK

Perform a comprehensive review of this content:

### 1. CONTENT ANALYSIS
- Is the information accurate and complete?
- Are there any gaps or missing elements?
- Does the content address the original request fully?
- Is the depth appropriate for the audience?

### 2. CONSISTENCY CHECK
- Is terminology used consistently throughout?
- Is the style consistent across all sections?
- Is the tone appropriate and consistent?
- Are there any contradictions?

### 3. QUALITY ASSESSMENT
- Is the content clear and well-organized?
- Are explanations easy to understand?
- Are examples helpful and relevant?
- Is the formatting appropriate?

### 4. IMPROVEMENTS
For each issue found, provide:
- The section number/location
- The issue description
- The recommended fix

After your review, provide the FINAL CONTENT with all improvements incorporated."""

    SECTION_FORMAT = """
### Section {section_number}: {title}

**Content:** {content}

**Key Points:** {key_points}

**Notes:** {notes}
"""

    ENHANCEMENT_TEMPLATE = """## CONTENT ENHANCEMENT TASK

**Section Number:** {section_number}
**Current Content:**
{current_content}

**Issues Identified:**
{issues}

**Enhancement Guidelines:**
{guidelines}

## YOUR TASK

Enhance this section to address the identified issues while maintaining consistency with the overall content.

Provide the enhanced section in the standard format."""

    FINAL_OUTPUT_TEMPLATE = """## FINAL OUTPUT

**Title:** {title}
**Domain:** {domain}
**Total Sections:** {total_sections}

### Overview
{overview}

### Content Style Guide
{content_style}

### Content

{sections}

### Summary
{summary}

### Additional Notes
{notes}
"""

    def __init__(self):
        """Initialize the ReFlect prompt builder."""
        pass
    
    def build_system_prompt(self) -> str:
        """
        Build the system prompt for ReFlect agent.
        
        Returns:
            str: System prompt
        """
        return self.SYSTEM_PROMPT
    
    def build_review_prompt(
        self,
        domain: str,
        title: str,
        query: str,
        master_plan: Dict[str, Any],
        sections: List[Any],
        domain_guidelines: str
    ) -> str:
        """
        Build the review prompt for the complete content.
        
        Args:
            domain: Domain type
            title: Content title
            query: Original user query
            master_plan: Master plan data
            sections: List of generated sections
            domain_guidelines: Domain-specific guidelines
            
        Returns:
            str: Formatted review prompt
        """
        # Format sections
        content_sections = ""
        for section in sections:
            if hasattr(section, 'scene_number'):
                # Legacy Scene object support
                content_sections += self.SECTION_FORMAT.format(
                    section_number=section.scene_number,
                    title=section.title,
                    content=section.description,
                    key_points=", ".join(section.visual_elements) if section.visual_elements else "None specified",
                    notes=section.notes or "None"
                )
            elif isinstance(section, dict):
                content_sections += self.SECTION_FORMAT.format(
                    section_number=section.get("section_number", "?"),
                    title=section.get("title", "Untitled"),
                    content=section.get("content", section.get("description", "")),
                    key_points=section.get("key_points", "None specified"),
                    notes=section.get("notes", "None")
                )
        
        return self.REVIEW_TEMPLATE.format(
            domain=domain,
            title=title,
            query=query,
            context_description=master_plan.get("context_description", master_plan.get("world_setting", "Not specified")),
            content_style=master_plan.get("content_style", master_plan.get("visual_style", "Standard")),
            tone=master_plan.get("tone", "Professional"),
            content_sections=content_sections,
            domain_guidelines=domain_guidelines
        )
    
    def build_enhancement_prompt(
        self,
        section_number: int,
        current_content: str,
        issues: List[str],
        guidelines: str
    ) -> str:
        """
        Build a prompt for enhancing a specific section.
        
        Args:
            section_number: Section to enhance
            current_content: Current section content
            issues: List of issues to address
            guidelines: Enhancement guidelines
            
        Returns:
            str: Enhancement prompt
        """
        issues_str = "\n".join([f"- {issue}" for issue in issues])
        
        return self.ENHANCEMENT_TEMPLATE.format(
            section_number=section_number,
            current_content=current_content,
            issues=issues_str,
            guidelines=guidelines
        )
    
    def build_coherence_check_prompt(
        self,
        sections: List[Any]
    ) -> str:
        """
        Build a prompt for checking overall coherence.
        
        Args:
            sections: All sections in the content
            
        Returns:
            str: Coherence check prompt
        """
        section_summaries = []
        for s in sections:
            if hasattr(s, 'scene_number'):
                section_summaries.append(f"Section {s.scene_number}: {s.title} - {s.description[:100]}...")
            elif isinstance(s, dict):
                content = s.get('content', s.get('description', ''))[:100]
                section_summaries.append(f"Section {s.get('section_number', '?')}: {s.get('title', 'Untitled')} - {content}...")
        
        summaries_str = "\n".join(section_summaries)
        
        return f"""## COHERENCE CHECK

Review these section summaries for content coherence:

{summaries_str}

Check for:
1. Logical progression of content
2. Consistent terminology
3. No contradictions between sections
4. Smooth transitions
5. Appropriate depth throughout

Identify any coherence issues and suggest fixes."""
    
    def build_final_output_prompt(
        self,
        title: str,
        domain: str,
        overview: str,
        content_style: str,
        sections: List[Any],
        summary: str = "",
        notes: str = ""
    ) -> str:
        """
        Build the final content output.
        
        Args:
            title: Content title
            domain: Domain type
            overview: Content overview
            content_style: Content style guide
            sections: All sections
            summary: Final summary
            notes: Additional notes
            
        Returns:
            str: Final formatted content
        """
        sections_str = ""
        for section in sections:
            if hasattr(section, 'scene_number'):
                sections_str += self.SECTION_FORMAT.format(
                    section_number=section.scene_number,
                    title=section.title,
                    content=section.description,
                    key_points=", ".join(section.visual_elements) if section.visual_elements else "None",
                    notes=section.notes or "None"
                )
            elif isinstance(section, dict):
                sections_str += self.SECTION_FORMAT.format(
                    section_number=section.get("section_number", "?"),
                    title=section.get("title", "Untitled"),
                    content=section.get("content", section.get("description", "")),
                    key_points=section.get("key_points", "None"),
                    notes=section.get("notes", "None")
                )
        
        return self.FINAL_OUTPUT_TEMPLATE.format(
            title=title,
            domain=domain,
            total_sections=len(sections),
            overview=overview,
            content_style=content_style,
            sections=sections_str,
            summary=summary or "See sections above for complete content.",
            notes=notes or "No additional notes."
        )


# Singleton instance
_reflect_builder: Optional[ReFlectPromptBuilder] = None


def get_reflect_prompt_builder() -> ReFlectPromptBuilder:
    """Get the ReFlect prompt builder singleton."""
    global _reflect_builder
    if _reflect_builder is None:
        _reflect_builder = ReFlectPromptBuilder()
    return _reflect_builder
