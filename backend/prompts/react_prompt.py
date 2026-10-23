"""
ReAct agent prompt builder for content generation.
"""

from typing import Dict, Any, Optional, List


class ReActPromptBuilder:
    """
    Builder for ReAct (reasoning + acting) agent prompts.
    
    The ReAct agent is responsible for:
    - Generating detailed content based on the master plan
    - Using Thought → Action → Observation loops
    - Querying RAG for domain knowledge
    - Updating memory with content details
    """
    
    SYSTEM_PROMPT = """You are ReAct, an expert content generation agent. You use a Thought-Action-Observation loop to create detailed, high-quality content.

You have access to three types of actions:
1. **llm_call**: Generate content using your reasoning (use for writing, analysis, explanations)
2. **rag_search**: Search for domain-specific knowledge and best practices
3. **memory_update**: Store important information for consistency
4. **memory_query**: Retrieve previously stored information

Your goal is to generate content that is:
- Faithful to the master plan
- Consistent with previously generated content
- Following domain-specific guidelines
- Detailed, accurate, and helpful

Always think before acting. Your observations inform your next thought."""

    CONTENT_GENERATION_TEMPLATE = """## CONTENT GENERATION TASK

**Domain:** {domain}
**Section Number:** {section_number} of {total_sections}
**Section Title:** {section_title}
**Section Outline:** {section_outline}

## MASTER PLAN CONTEXT

**Title:** {content_title}
**Context:** {context_description}
**Style:** {content_style}
**Guidelines:** {content_guidelines}
**Tone:** {tone}

## KEY ELEMENTS
{key_elements}

## DOMAIN GUIDELINES
{domain_guidelines}

## MEMORY CONTEXT
{memory_context}

## YOUR TASK

Generate detailed content following the Thought-Action-Observation pattern.

For each step:
1. **Thought**: Reason about what you need to do next
2. **Action**: Choose an action type and input
   - `llm_call`: [what to generate]
   - `rag_search`: [what to search for]
   - `memory_update`: [what to store]
   - `memory_query`: [what to retrieve]
3. **Observation**: Process the result

Continue until the content is complete, then output the final section in this format:

## FINAL CONTENT

**Section Number:** {section_number}
**Title:** [title]
**Content:** [detailed content - multiple paragraphs as needed]
**Key Points:** [list of key points]
**Examples:** [any examples or illustrations]
**Summary:** [brief summary]
**Notes:** [any additional notes]

Begin with your first Thought."""

    ACTION_FORMAT = """
**Thought:** {thought}
**Action:** {action_type}
**Action Input:** {action_input}
"""

    OBSERVATION_FORMAT = """
**Observation:** {observation}
"""

    def __init__(self):
        """Initialize the ReAct prompt builder."""
        pass
    
    def build_system_prompt(self) -> str:
        """
        Build the system prompt for ReAct agent.
        
        Returns:
            str: System prompt
        """
        return self.SYSTEM_PROMPT
    
    def build_content_prompt(
        self,
        domain: str,
        section_number: int,
        total_sections: int,
        section_title: str,
        section_outline: str,
        master_plan: Dict[str, Any],
        domain_guidelines: str,
        memory_context: str = "No previous context."
    ) -> str:
        """
        Build the content generation prompt.
        
        Args:
            domain: Domain type
            section_number: Current section number
            total_sections: Total number of sections
            section_title: Title of this section
            section_outline: Brief outline from master plan
            master_plan: Complete master plan data
            domain_guidelines: Domain-specific guidelines
            memory_context: Context from TME
            
        Returns:
            str: Formatted content generation prompt
        """
        # Format key elements
        key_elements = master_plan.get("key_elements", [])
        if key_elements:
            elements_str = "\n".join([
                f"- **{e.get('name', 'Item')}**: {e.get('description', 'No description')}"
                for e in key_elements
            ])
        else:
            elements_str = "No specific elements defined."
        
        return self.CONTENT_GENERATION_TEMPLATE.format(
            domain=domain,
            section_number=section_number,
            total_sections=total_sections,
            section_title=section_title,
            section_outline=section_outline,
            content_title=master_plan.get("title", "Untitled"),
            context_description=master_plan.get("context_description", "Not specified"),
            content_style=master_plan.get("content_style", "Standard"),
            content_guidelines=master_plan.get("content_guidelines", "Standard guidelines"),
            tone=master_plan.get("tone", "Professional"),
            key_elements=elements_str,
            domain_guidelines=domain_guidelines,
            memory_context=memory_context
        )
    
    def build_continuation_prompt(
        self,
        previous_content: str,
        observation: str
    ) -> str:
        """
        Build a continuation prompt after an observation.
        
        Args:
            previous_content: Previous thoughts and actions
            observation: Latest observation
            
        Returns:
            str: Continuation prompt
        """
        return f"""{previous_content}

{self.OBSERVATION_FORMAT.format(observation=observation)}

Continue with your next Thought, or if the content is complete, output the FINAL CONTENT."""
    
    def build_consistency_check_prompt(
        self,
        current_content: str,
        previous_sections: List[str],
        master_plan: Dict[str, Any]
    ) -> str:
        """
        Build a prompt for checking content consistency.
        
        Args:
            current_content: The current content
            previous_sections: List of previous section summaries
            master_plan: The master plan
            
        Returns:
            str: Consistency check prompt
        """
        prev_sections_str = "\n".join([
            f"Section {i+1}: {s}" for i, s in enumerate(previous_sections)
        ])
        
        return f"""## CONSISTENCY CHECK

**Master Plan Title:** {master_plan.get('title', 'Untitled')}
**Content Style:** {master_plan.get('content_style', 'Standard')}

**Previous Sections:**
{prev_sections_str}

**Current Content:**
{current_content}

Check for:
1. Terminology consistency (same terms used throughout)
2. Style consistency (tone, format, level of detail)
3. Logical flow and continuity
4. No contradictions with previous sections
5. Appropriate depth and coverage

List any inconsistencies found, or confirm the content is consistent."""
    
    def parse_action(self, response: str) -> Optional[Dict[str, str]]:
        """
        Parse an action from the agent's response.
        
        Args:
            response: Agent response text
            
        Returns:
            Optional[Dict[str, str]]: Parsed action or None
        """
        lines = response.strip().split('\n')
        action_type = None
        action_input = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('**Action:**'):
                action_type = line.replace('**Action:**', '').strip()
            elif line.startswith('**Action Input:**'):
                action_input = line.replace('**Action Input:**', '').strip()
        
        if action_type and action_input:
            return {
                "action_type": action_type,
                "action_input": action_input
            }
        return None


# Singleton instance
_react_builder: Optional[ReActPromptBuilder] = None


def get_react_prompt_builder() -> ReActPromptBuilder:
    """Get the ReAct prompt builder singleton."""
    global _react_builder
    if _react_builder is None:
        _react_builder = ReActPromptBuilder()
    return _react_builder
