"""
PreAct agent prompt builder for planning and dynamic template generation.

This is the prompt building component for the THINKER in ThinkerLLM.
PreAct creates structured reasoning plans before any action is taken.
"""

from typing import Dict, Any, Optional, List
import json


class PreActPromptBuilder:
    """
    Builder for preAct (planning) agent prompts.
    
    The preAct agent is responsible for:
    - Analyzing the user query and domain
    - Detecting domain from query dynamically
    - Creating a master plan with logical steps
    - Defining domain-specific skills and capabilities
    - Establishing template structure for generation
    
    Enhanced for ThinkerLLM:
    - Dynamic template generation planning
    - Domain detection and skill assignment
    - Instructional Designer skill inclusion
    - Unique capability key generation
    """
    
    SYSTEM_PROMPT = """You are PreAct, the PLANNER component of ThinkerLLM.

## YOUR ROLE: PLAN ONLY
You CREATE the execution plan. You do NOT create the actual content.
The ReAct agent will EXECUTE your plan and create the actual content.

## WHAT YOU DO
- Analyze the user's request
- Break it down into clear, actionable steps
- Define what each step should produce
- Set constraints and success criteria

## WHAT YOU DON'T DO
- Don't write the actual course content
- Don't write the actual analysis
- Don't create the final deliverable
- Just create the PLAN for ReAct to follow

## EXAMPLE
User: "Create a Python course"

Your output (plan):
- Step 1: Create Introduction module (ReAct will write the actual intro content)
- Step 2: Create Variables module (ReAct will write the actual lesson)
- Step 3: Create Functions module (ReAct will write the actual lesson)

You output the PLAN. ReAct creates the ACTUAL CONTENT.

Your outputs MUST be in JSON format for ReAct to parse and execute."""
    
    TEMPLATE_SYSTEM_PROMPT = """You are PreAct, the THINKER component of ThinkerLLM - specialized in dynamic template generation.

Your role is to create comprehensive plans for generating domain-specific templates.

CRITICAL RULES:
1. "Instructional Designer" MUST be included in every domain's skills
2. Capability keys MUST be unique to each domain (no generic keys)
3. All plans must follow the required JSON schema
4. Each step must produce actionable output for ReAct

Your plan enables:
- Dynamic domain detection from user queries
- Unique template generation per domain
- Validation by ReFlect agent
- Storage in TME memory"""

    PLANNING_TEMPLATE = """## PLANNING TASK

**Domain:** {domain}
**User Query:** {query}

## DOMAIN GUIDELINES

**Planning Rules:**
{planning_rules}

**Camera Rules:**
{camera_rules}

**Tone Guidelines:**
{tone_guidelines}

**Visual Style:**
{visual_style}

## YOUR TASK

Create a comprehensive Master Plan for this storyboard. Your plan must include:

1. **TITLE**: A compelling title for this storyboard

2. **WORLD SETTING**: Describe the environment, time period, and context where this storyboard takes place

3. **CHARACTERS** (if applicable): Define any characters, their roles, appearances, and personalities

4. **VISUAL STYLE RULES**: Specific visual guidelines for this storyboard based on the domain and query

5. **CAMERA RULES**: Specific camera direction guidelines for this storyboard

6. **TONE**: The emotional tone and mood throughout

7. **SCENE OUTLINE**: A numbered list of {max_scenes} scenes, each with:
   - Scene number
   - Brief title
   - One-sentence description of what happens
   - Key visual element or action

## OUTPUT FORMAT

Provide your Master Plan in clear, structured format. Be specific and actionable. Each element should directly inform the scene generation process.

Begin your response with your thinking process, then output the Master Plan."""

    TEMPLATE_PLANNING_TEMPLATE = """## DYNAMIC TEMPLATE GENERATION TASK

**Detected Domain:** {domain}
**User Query:** {query}

## DOMAIN-SPECIFIC REQUIREMENTS

**Suggested Skills (MUST include Instructional Designer):**
{suggested_skills}

**Suggested Capability Keys (must be unique to this domain):**
{suggested_capabilities}

## YOUR TASK

Create a comprehensive reasoning plan for generating a dynamic domain template.

Your plan MUST output this JSON structure:

```json
{{
    "title": "Template generation for {domain} domain",
    "detected_domain": "{domain}",
    "task_understanding": "Your understanding of what needs to be generated",
    "approach": "How you will generate this template",
    "domain_skills": [
        "Instructional Designer",
        "...other domain-specific skills..."
    ],
    "domain_capabilities": [
        "unique_capability_key_1",
        "unique_capability_key_2",
        "...domain-specific keys..."
    ],
    "steps": [
        {{
            "step_number": 1,
            "title": "Analyze domain requirements",
            "description": "What this step does",
            "expected_output": "What this step produces",
            "dependencies": []
        }},
        {{
            "step_number": 2,
            "title": "Generate domain skills",
            "description": "Create skill list with Instructional Designer",
            "expected_output": "Complete skills array",
            "dependencies": [1]
        }},
        {{
            "step_number": 3,
            "title": "Generate unique capabilities",
            "description": "Create domain-specific capability keys",
            "expected_output": "Unique capability object",
            "dependencies": [1]
        }},
        {{
            "step_number": 4,
            "title": "Build template structure",
            "description": "Compile complete template with metadata",
            "expected_output": "Complete template JSON",
            "dependencies": [2, 3]
        }},
        {{
            "step_number": 5,
            "title": "Validate and finalize",
            "description": "Ensure all requirements met",
            "expected_output": "Validated template ready for ReFlect",
            "dependencies": [4]
        }}
    ],
    "constraints": [
        "Instructional Designer MUST be in skills",
        "All capability keys must be unique to {domain}",
        "Follow required JSON schema",
        "No duplicate keys across domains"
    ],
    "success_criteria": [
        "Template contains Instructional Designer skill",
        "All capability keys are unique",
        "JSON schema is valid",
        "Content is domain-specific and meaningful"
    ],
    "estimated_complexity": "moderate"
}}
```

## CRITICAL REQUIREMENTS

1. **INSTRUCTIONAL DESIGNER**: This skill MUST be the first item in domain_skills array
2. **UNIQUE KEYS**: capability keys must be specific to {domain}, not generic
3. **SCHEMA**: Output must be valid JSON matching the structure above
4. **STEPS**: Include at least 4-5 actionable steps

Output ONLY the JSON plan, no additional text."""

    def __init__(self):
        """Initialize the PreAct prompt builder."""
        pass
    
    def build_system_prompt(self, for_template: bool = False) -> str:
        """
        Build the system prompt for preAct agent.
        
        Args:
            for_template: If True, use template-specific system prompt
        
        Returns:
            str: System prompt
        """
        if for_template:
            return self.TEMPLATE_SYSTEM_PROMPT
        return self.SYSTEM_PROMPT
    
    def build_planning_prompt(
        self,
        domain: str,
        query: str,
        domain_template: Dict[str, str],
        max_scenes: int = 6,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Build the planning prompt for preAct agent.
        
        Args:
            domain: Domain type
            query: User query
            domain_template: Domain-specific guidelines
            max_scenes: Maximum number of scenes to plan
            additional_context: Optional additional context
            
        Returns:
            str: Formatted planning prompt
        """
        prompt = self.PLANNING_TEMPLATE.format(
            domain=domain,
            query=query,
            planning_rules=domain_template.get("planning_rules", "No specific rules."),
            camera_rules=domain_template.get("camera_rules", "Standard camera work."),
            tone_guidelines=domain_template.get("tone_guidelines", "Professional and clear."),
            visual_style=domain_template.get("visual_style", "Clean and modern."),
            max_scenes=max_scenes
        )
        
        if additional_context:
            prompt += f"\n\n## ADDITIONAL CONTEXT\n{additional_context}"
        
        return prompt
    
    def build_template_planning_prompt(
        self,
        domain: str,
        query: str,
        suggested_skills: List[str] = None,
        suggested_capabilities: List[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Build a planning prompt for dynamic template generation.
        
        Args:
            domain: Detected domain type
            query: User query
            suggested_skills: List of suggested domain skills
            suggested_capabilities: List of suggested capability keys
            additional_context: Optional additional context
            
        Returns:
            str: Formatted template planning prompt
        """
        # Ensure Instructional Designer is always first
        skills = suggested_skills or ["Instructional Designer"]
        if "Instructional Designer" not in skills:
            skills = ["Instructional Designer"] + skills
        elif skills[0] != "Instructional Designer":
            skills.remove("Instructional Designer")
            skills = ["Instructional Designer"] + skills
        
        capabilities = suggested_capabilities or []
        
        prompt = self.TEMPLATE_PLANNING_TEMPLATE.format(
            domain=domain,
            query=query,
            suggested_skills=json.dumps(skills, indent=2),
            suggested_capabilities=json.dumps(capabilities, indent=2)
        )
        
        if additional_context:
            prompt += f"\n\n## ADDITIONAL CONTEXT\n{additional_context}"
        
        return prompt
    
    def build_domain_detection_prompt(self, query: str) -> str:
        """
        Build a prompt for detecting the domain from user query.
        
        Args:
            query: User query
            
        Returns:
            str: Domain detection prompt
        """
        return f"""Analyze this user query and detect the most appropriate domain.

## USER QUERY
{query}

## AVAILABLE DOMAINS
- healthcare: Medical, clinical, patient care, hospitals, health
- finance: Banking, investment, stocks, loans, accounting
- hr: Human resources, hiring, employees, payroll, benefits
- cloud: Cloud computing, AWS, Azure, DevOps, infrastructure
- software: Development, programming, APIs, testing, coding
- sales: CRM, leads, deals, revenue, customers
- education: Learning, teaching, courses, students, training
- marketing: Campaigns, branding, advertising, social media
- legal: Law, contracts, compliance, regulations
- manufacturing: Production, factories, quality control, supply chain

## OUTPUT FORMAT
Output ONLY the domain name (lowercase, single word) that best matches the query.
If no specific domain matches, output "general".

Domain:"""
    
    def build_refinement_prompt(
        self,
        original_plan: str,
        feedback: str
    ) -> str:
        """
        Build a prompt for refining an existing plan.
        
        Args:
            original_plan: The original master plan
            feedback: Feedback or issues to address
            
        Returns:
            str: Refinement prompt
        """
        return f"""## PLAN REFINEMENT TASK

**Original Plan:**
{original_plan}

**Feedback/Issues:**
{feedback}

## YOUR TASK

Refine the Master Plan to address the feedback while maintaining the original structure and intent. Only modify what's necessary to address the issues.

Provide the complete refined Master Plan."""


# Singleton instance
_preact_builder: Optional[PreActPromptBuilder] = None


def get_preact_prompt_builder() -> PreActPromptBuilder:
    """Get the PreAct prompt builder singleton."""
    global _preact_builder
    if _preact_builder is None:
        _preact_builder = PreActPromptBuilder()
    return _preact_builder

