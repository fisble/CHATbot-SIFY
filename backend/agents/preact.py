"""
PreAct Agent - Pre-Action Reasoning ("Think Before Acting")

PreAct creates a structured reasoning plan BEFORE producing any output.
Pattern: Plan → Execute → Answer

This is the THINKER component of ThinkerLLM - adding thinking capacity to non-thinking LLMs.
Like Cursor's Plan Mode, PreAct:
1. Understands the task
2. Detects the domain dynamically
3. Breaks it down into logical steps
4. Identifies requirements and constraints
5. Creates a clear execution plan with domain-specific keys
6. Includes required skills (e.g., Instructional Designer)

Use cases:
- Dynamic template generation
- Code generation
- Summaries
- Data classification
- Writing tasks
- Business logic execution
"""

from typing import AsyncGenerator, Optional, Dict, Any, List
import json
import re
import uuid
import asyncio
from datetime import datetime

from .base import BaseAgent, AgentContext
from models.schemas import AgentEvent, AgentName, AgentEventType, MasterPlan
from config import settings


# Domain detection patterns and keywords
DOMAIN_PATTERNS = {
    "healthcare": ["medical", "health", "clinical", "patient", "hospital", "doctor", "nurse", "diagnosis", "treatment", "pharma", "drug"],
    "finance": ["finance", "banking", "investment", "stock", "trading", "loan", "credit", "insurance", "accounting", "budget", "revenue"],
    "hr": ["hr", "human resources", "employee", "hiring", "recruitment", "onboarding", "payroll", "benefits", "performance review", "talent"],
    "cloud": ["cloud", "aws", "azure", "gcp", "kubernetes", "docker", "devops", "infrastructure", "serverless", "microservices"],
    "software": ["software", "development", "programming", "code", "api", "database", "testing", "agile", "scrum", "deployment"],
    "sales": ["sales", "crm", "lead", "pipeline", "prospect", "deal", "quota", "revenue", "customer", "conversion"],
    "education": ["education", "learning", "teaching", "course", "curriculum", "student", "training", "tutorial", "lesson", "classroom"],
    "marketing": ["marketing", "campaign", "brand", "advertising", "social media", "seo", "content", "promotion", "audience", "engagement"],
    "legal": ["legal", "law", "contract", "compliance", "regulation", "litigation", "attorney", "court", "rights", "policy"],
    "manufacturing": ["manufacturing", "production", "factory", "assembly", "quality control", "supply chain", "inventory", "lean", "six sigma"],
}

# Domain-specific skill sets (Instructional Designer is ALWAYS included)
DOMAIN_SKILLS = {
    "healthcare": ["Clinical Trainer", "Medical Writer", "Patient Educator", "Compliance Specialist"],
    "finance": ["Financial Analyst", "Risk Assessor", "Compliance Officer", "Investment Advisor"],
    "hr": ["Talent Developer", "Policy Writer", "Employee Relations Specialist", "Compensation Analyst"],
    "cloud": ["Solutions Architect", "DevOps Engineer", "Security Specialist", "Cost Optimizer"],
    "software": ["Technical Writer", "Code Reviewer", "Architecture Designer", "QA Specialist"],
    "sales": ["Sales Trainer", "CRM Specialist", "Negotiation Coach", "Pipeline Analyst"],
    "education": ["Curriculum Designer", "Assessment Developer", "Learning Technologist", "Subject Expert"],
    "marketing": ["Content Strategist", "Brand Manager", "Analytics Expert", "Campaign Designer"],
    "legal": ["Legal Writer", "Contract Analyst", "Compliance Trainer", "Policy Developer"],
    "manufacturing": ["Process Engineer", "Quality Trainer", "Safety Specialist", "Lean Consultant"],
    "default": ["Content Creator", "Process Designer", "Quality Analyst", "Documentation Specialist"],
}

# Domain-specific capability keys (unique per domain, no duplication)
DOMAIN_CAPABILITIES = {
    "healthcare": ["clinical_protocols", "patient_safety_guidelines", "hipaa_compliance", "medical_terminology"],
    "finance": ["risk_assessment_framework", "regulatory_compliance", "financial_modeling", "audit_procedures"],
    "hr": ["policy_framework", "employee_lifecycle", "performance_metrics", "benefits_administration"],
    "cloud": ["infrastructure_patterns", "security_protocols", "cost_optimization", "disaster_recovery"],
    "software": ["development_standards", "code_quality_metrics", "api_documentation", "testing_frameworks"],
    "sales": ["sales_methodology", "pipeline_management", "objection_handling", "closing_techniques"],
    "education": ["learning_objectives", "assessment_criteria", "engagement_strategies", "progression_paths"],
    "marketing": ["brand_guidelines", "content_strategy", "audience_targeting", "campaign_metrics"],
    "legal": ["contract_templates", "compliance_checklist", "risk_mitigation", "regulatory_mapping"],
    "manufacturing": ["process_workflows", "quality_standards", "safety_protocols", "efficiency_metrics"],
    "default": ["content_structure", "quality_guidelines", "process_flow", "output_standards"],
}

# Domain-specific deep dive focus areas for intensive analysis
DOMAIN_DEEP_DIVE = {
    "education": {
        "focus_areas": [
            "Learning objectives (what will learners be able to DO after?)",
            "Assessment strategy (how to measure learning?)",
            "Engagement methods (activities, interactivity, gamification)",
            "Prerequisite mapping (what must learners already know?)",
            "Progression design (beginner → intermediate → advanced)",
            "Content chunking (optimal module/lesson length)",
            "Practice opportunities (exercises, labs, projects)",
            "Feedback mechanisms (how learners know they're on track)"
        ],
        "key_questions": [
            "What are the specific, measurable learning outcomes?",
            "What prior knowledge is assumed?",
            "What assessment types are appropriate (quiz, project, portfolio)?",
            "What's the optimal learning path progression?"
        ],
        "success_metrics": [
            "Learner can demonstrate skill X",
            "Knowledge retention after Y weeks",
            "Completion rate of modules",
            "Assessment pass rates"
        ]
    },
    "software": {
        "focus_areas": [
            "Architecture decisions (monolith vs microservices, patterns)",
            "Technology stack (languages, frameworks, databases)",
            "API design (REST, GraphQL, contracts)",
            "Testing strategy (unit, integration, e2e coverage)",
            "Security considerations (auth, data protection, OWASP)",
            "Performance requirements (latency, throughput, scale)",
            "Deployment strategy (CI/CD, environments, rollback)",
            "Observability (logging, monitoring, alerting)"
        ],
        "key_questions": [
            "What are the non-functional requirements (performance, security)?",
            "What's the expected scale and growth?",
            "What existing systems need integration?",
            "What's the team's tech stack expertise?"
        ],
        "success_metrics": [
            "Code coverage percentage",
            "Response time under load",
            "Deployment frequency",
            "Mean time to recovery"
        ]
    },
    "finance": {
        "focus_areas": [
            "Risk assessment (market, credit, operational)",
            "Regulatory compliance (SOX, Basel, local regulations)",
            "Financial modeling (forecasts, scenarios, sensitivity)",
            "Audit trail requirements",
            "Stakeholder reporting needs",
            "Data accuracy and validation",
            "Historical trend analysis",
            "Benchmark comparisons"
        ],
        "key_questions": [
            "What regulatory frameworks apply?",
            "What's the risk tolerance level?",
            "Who are the key stakeholders for reporting?",
            "What's the time horizon for analysis?"
        ],
        "success_metrics": [
            "Compliance audit pass",
            "Forecast accuracy",
            "Risk-adjusted returns",
            "Stakeholder satisfaction"
        ]
    },
    "sales": {
        "focus_areas": [
            "Sales methodology (consultative, SPIN, challenger)",
            "Pipeline management (stages, velocity, conversion)",
            "Objection handling frameworks",
            "Competitive positioning",
            "Value proposition articulation",
            "Customer segmentation",
            "Closing techniques",
            "Account management strategies"
        ],
        "key_questions": [
            "What's the average deal size and sales cycle?",
            "What are the primary customer objections?",
            "Who are the main competitors?",
            "What's the current conversion rate?"
        ],
        "success_metrics": [
            "Win rate improvement",
            "Average deal size",
            "Sales cycle length",
            "Customer acquisition cost"
        ]
    },
    "marketing": {
        "focus_areas": [
            "Brand positioning and messaging",
            "Target audience personas",
            "Channel strategy (digital, traditional, hybrid)",
            "Content strategy and calendar",
            "Campaign measurement (KPIs, attribution)",
            "Competitive analysis",
            "Customer journey mapping",
            "Budget allocation"
        ],
        "key_questions": [
            "Who is the ideal customer profile?",
            "What's the primary marketing objective (awareness, leads, conversion)?",
            "What channels have proven most effective?",
            "What's the budget range?"
        ],
        "success_metrics": [
            "Brand awareness lift",
            "Lead generation volume",
            "Conversion rate",
            "Customer acquisition cost"
        ]
    },
    "hr": {
        "focus_areas": [
            "Policy framework compliance",
            "Employee lifecycle management",
            "Performance management systems",
            "Compensation and benefits structure",
            "Training and development programs",
            "Employee engagement strategies",
            "Diversity and inclusion initiatives",
            "Succession planning"
        ],
        "key_questions": [
            "What's the company size and structure?",
            "What are the current HR pain points?",
            "What compliance requirements apply?",
            "What's the organizational culture?"
        ],
        "success_metrics": [
            "Employee satisfaction score",
            "Retention rate",
            "Time to fill positions",
            "Training completion rates"
        ]
    },
    "healthcare": {
        "focus_areas": [
            "Clinical protocols and guidelines",
            "Patient safety considerations",
            "HIPAA and privacy compliance",
            "Evidence-based practice integration",
            "Care coordination workflows",
            "Quality metrics (HEDIS, CMS stars)",
            "Documentation requirements",
            "Interdisciplinary communication"
        ],
        "key_questions": [
            "What clinical specialty or setting?",
            "What are the key patient populations?",
            "What quality measures apply?",
            "What EHR/systems are in use?"
        ],
        "success_metrics": [
            "Patient outcomes improvement",
            "Compliance audit scores",
            "Patient satisfaction",
            "Readmission rates"
        ]
    },
    "cloud": {
        "focus_areas": [
            "Infrastructure patterns (IaC, containers, serverless)",
            "Security architecture (IAM, encryption, network)",
            "Cost optimization strategies",
            "Disaster recovery and business continuity",
            "Multi-cloud/hybrid considerations",
            "Observability and monitoring",
            "Compliance and governance",
            "Migration strategies"
        ],
        "key_questions": [
            "What cloud provider(s) are in use or preferred?",
            "What are the compliance requirements?",
            "What's the current infrastructure state?",
            "What's the budget for cloud spend?"
        ],
        "success_metrics": [
            "Uptime/availability percentage",
            "Cost per transaction/user",
            "Mean time to recovery",
            "Security incident count"
        ]
    },
    "default": {
        "focus_areas": [
            "Clear objective definition",
            "Stakeholder identification",
            "Resource requirements",
            "Timeline considerations",
            "Quality standards",
            "Risk identification",
            "Success measurement",
            "Communication plan"
        ],
        "key_questions": [
            "What's the primary objective?",
            "Who are the key stakeholders?",
            "What resources are available?",
            "What does success look like?"
        ],
        "success_metrics": [
            "Objective achieved",
            "Stakeholder satisfaction",
            "On-time delivery",
            "Quality standards met"
        ]
    }
}


class ReasoningStep:
    """A single step in the reasoning plan with rich metadata."""
    
    def __init__(
        self,
        step_number: int,
        title: str,
        description: str,
        expected_output: str,
        dependencies: List[int] = None,
        sub_steps: List[str] = None,
        estimated_effort: str = "15min",
        validation_criteria: List[str] = None,
        tools_needed: List[str] = None,
        priority: str = "important"
    ):
        self.step_number = step_number
        self.title = title
        self.description = description
        self.expected_output = expected_output
        self.dependencies = dependencies or []
        # Enhanced fields for intensive planning
        self.sub_steps = sub_steps or []
        self.estimated_effort = estimated_effort  # "5min", "15min", "30min", "1hr", "2hr+"
        self.validation_criteria = validation_criteria or []
        self.tools_needed = tools_needed or ["GENERATE"]
        self.priority = priority  # "critical", "important", "optional"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "title": self.title,
            "description": self.description,
            "expected_output": self.expected_output,
            "dependencies": self.dependencies,
            "sub_steps": self.sub_steps,
            "estimated_effort": self.estimated_effort,
            "validation_criteria": self.validation_criteria,
            "tools_needed": self.tools_needed,
            "priority": self.priority
        }


class ClarificationQuestion:
    """A contextual clarification question for the user to refine the plan."""
    
    def __init__(
        self,
        id: str,
        question: str,
        question_type: str = "boolean",  # "boolean", "choice", "text"
        options: List[str] = None,
        default: str = None,
        priority: str = "medium",  # "high", "medium", "low"
        reason: str = None  # Why this question matters
    ):
        self.id = id
        self.question = question
        self.question_type = question_type
        self.options = options or []
        self.default = default
        self.priority = priority
        self.reason = reason or "Helps clarify requirements"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "type": self.question_type,
            "options": self.options,
            "default": self.default,
            "priority": self.priority,
            "reason": self.reason
        }


class ReasoningPlan:
    """A structured reasoning plan created by PreAct with deep analysis."""
    
    def __init__(
        self,
        title: str,
        task_understanding: str,
        approach: str,
        steps: List[ReasoningStep],
        constraints: List[str],
        success_criteria: List[str],
        estimated_complexity: str,
        detected_domain: str = "default",
        domain_skills: List[str] = None,
        domain_capabilities: List[str] = None,
        template_id: str = None,
        clarification_questions: List[ClarificationQuestion] = None,
        chat_history: List[Dict] = None,
        # Deep analysis fields
        deep_analysis: Dict[str, Any] = None,
        requirements: Dict[str, Any] = None,
        risks_and_assumptions: Dict[str, Any] = None,
        strategy: Dict[str, Any] = None,
        estimated_total_effort: str = None
    ):
        self.title = title
        self.task_understanding = task_understanding
        self.approach = approach
        self.steps = steps
        self.constraints = constraints
        self.success_criteria = success_criteria
        self.estimated_complexity = estimated_complexity
        # Domain-specific fields for dynamic template generation
        self.detected_domain = detected_domain
        self.domain_skills = domain_skills or ["Instructional Designer"]
        self.domain_capabilities = domain_capabilities or []
        self.template_id = template_id or str(uuid.uuid4())
        self.created_at = datetime.utcnow().isoformat()
        # Chat/refinement fields
        self.clarification_questions = clarification_questions or []
        self.chat_history = chat_history or []
        # Deep analysis fields for intensive planning
        self.deep_analysis = deep_analysis or {
            "audience": {"primary": "General", "skill_level": "intermediate", "prerequisites": [], "goals": []},
            "stakeholders": [],
            "context": "",
            "motivation": ""
        }
        self.requirements = requirements or {
            "explicit": [],
            "implicit": [],
            "out_of_scope": []
        }
        self.risks_and_assumptions = risks_and_assumptions or {
            "assumptions": [],
            "risks": [],
            "mitigations": []
        }
        self.strategy = strategy or {
            "alternatives_considered": [],
            "selected_approach": "",
            "rationale": ""
        }
        self.estimated_total_effort = estimated_total_effort or self._calculate_total_effort()
    
    def _calculate_total_effort(self) -> str:
        """Calculate total effort from step estimates."""
        effort_map = {"5min": 5, "15min": 15, "30min": 30, "1hr": 60, "2hr+": 120}
        total_minutes = sum(effort_map.get(s.estimated_effort, 15) for s in self.steps)
        if total_minutes < 60:
            return f"{total_minutes}min"
        elif total_minutes < 120:
            return "1-2 hours"
        else:
            return f"{total_minutes // 60}+ hours"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "task_understanding": self.task_understanding,
            "approach": self.approach,
            "steps": [s.to_dict() for s in self.steps],
            "constraints": self.constraints,
            "success_criteria": self.success_criteria,
            "estimated_complexity": self.estimated_complexity,
            # Domain-specific metadata for template generation
            "detected_domain": self.detected_domain,
            "domain_skills": self.domain_skills,
            "domain_capabilities": self.domain_capabilities,
            "template_id": self.template_id,
            "created_at": self.created_at,
            # Chat/refinement fields
            "clarification_questions": [q.to_dict() for q in self.clarification_questions],
            "chat_history": self.chat_history,
            # Deep analysis fields
            "deep_analysis": self.deep_analysis,
            "requirements": self.requirements,
            "risks_and_assumptions": self.risks_and_assumptions,
            "strategy": self.strategy,
            "estimated_total_effort": self.estimated_total_effort,
            "metadata": {
                "generated_by": "thinker-llm-preact-v2",
                "includes_instructional_designer": "Instructional Designer" in self.domain_skills,
                "analysis_depth": "intensive"
            }
        }


class PreActAgent(BaseAgent):
    """
    PreAct Agent - Pre-Action Reasoning (THE THINKER)
    
    "Think Before Acting" - Like Cursor's Plan Mode
    
    Creates a structured reasoning plan BEFORE producing output:
    1. Detect the domain from user query (dynamic domain detection)
    2. Understand what the user wants
    3. Break the task into logical steps
    4. Identify constraints and requirements
    5. Generate domain-specific skills (always includes Instructional Designer)
    6. Generate unique capability keys per domain
    7. Plan the approach
    8. Present plan for execution by ReAct
    
    This is the THINKER component - adding thinking capacity to non-thinking LLMs.
    """
    
    SYSTEM_PROMPT = """You are PreAct, the THINKER component of ThinkerLLM - an advanced planning agent.

Your role is to perform DEEP, MULTI-PHASE ANALYSIS before creating any plan. You always THINK INTENSIVELY BEFORE ACTING.

## CRITICAL: TASK TYPE DETECTION

FIRST determine what the user ACTUALLY wants:
- If they ask a QUESTION → Plan to ANSWER the question (not create a video about it)
- If they ask for ANALYSIS → Plan to CREATE analysis content (not a video)
- If they ask for a COURSE → Plan to CREATE course content (lessons, exercises)
- If they ask for a GUIDE → Plan to CREATE a guide document
- ONLY if they explicitly say "video", "storyboard", "animation", "film" → Plan video content

DO NOT default to video/storyboard production. This is a GENERAL AI assistant, not a video production tool.

## ANALYSIS PHASES (Execute ALL phases before planning)

### PHASE 1: CONTEXT ANALYSIS
- WHAT TYPE of output does the user actually want? (document, analysis, course, guide, answer, etc.)
- WHO is the target audience? (skill level, background, goals)
- WHAT stakeholders are involved or affected?
- WHY is this being requested? (underlying motivation)

### PHASE 2: REQUIREMENTS EXTRACTION  
- EXPLICIT requirements (directly stated in query)
- IMPLICIT requirements (inferred from context)
- PREREQUISITES (what must exist before starting)
- DEPENDENCIES (external factors, tools, knowledge needed)

### PHASE 3: CONSTRAINTS & RISKS
- TIME constraints (deadlines, duration limits)
- RESOURCE constraints (budget, tools, access)
- QUALITY constraints (standards, compliance)
- RISKS (what could go wrong, edge cases)
- ASSUMPTIONS (what are we assuming to be true)

### PHASE 4: STRATEGY SELECTION
- ALTERNATIVE approaches considered
- TRADE-OFFS between approaches
- SELECTED strategy and WHY
- SUCCESS metrics (measurable outcomes)

## OUTPUT FORMAT

Output your comprehensive reasoning plan in this JSON format:
{
    "title": "Descriptive title for this task",
    "detected_domain": "healthcare/finance/hr/cloud/software/sales/education/marketing/legal/manufacturing",
    
    "deep_analysis": {
        "audience": {
            "primary": "Main target audience description",
            "skill_level": "beginner/intermediate/advanced/mixed",
            "prerequisites": ["Required knowledge or skills"],
            "goals": ["What they want to achieve"]
        },
        "stakeholders": ["List of stakeholders affected"],
        "context": "When/where/how this will be used",
        "motivation": "Why this is being requested"
    },
    
    "requirements": {
        "explicit": ["Directly stated requirements"],
        "implicit": ["Inferred requirements"],
        "out_of_scope": ["What this does NOT include"]
    },
    
    "risks_and_assumptions": {
        "assumptions": ["Things we assume to be true"],
        "risks": ["Potential issues or challenges"],
        "mitigations": ["How we'll address risks"]
    },
    
    "strategy": {
        "alternatives_considered": [
            {"approach": "Alternative 1", "pros": ["..."], "cons": ["..."]},
            {"approach": "Alternative 2", "pros": ["..."], "cons": ["..."]}
        ],
        "selected_approach": "The chosen strategy",
        "rationale": "Why this approach was selected"
    },
    
    "task_understanding": "Comprehensive understanding of what the user needs",
    "approach": "Detailed description of the execution strategy",
    
    "domain_skills": ["Instructional Designer", "...other domain-specific skills..."],
    "domain_capabilities": ["unique_capability_key_1", "unique_capability_key_2"],
    
    "steps": [
        {
            "step_number": 1,
            "title": "Step title",
            "description": "Detailed description of what this step does",
            "expected_output": "Specific deliverable from this step",
            "dependencies": [],
            "sub_steps": ["Detailed sub-task 1", "Detailed sub-task 2", "Detailed sub-task 3"],
            "estimated_effort": "5min/15min/30min/1hr/2hr+",
            "validation_criteria": ["How to verify this step is complete"],
            "tools_needed": ["GENERATE", "SEARCH", "ANALYZE"],
            "priority": "critical/important/optional"
        }
    ],
    
    "constraints": ["Specific limitations or rules"],
    "success_criteria": ["Measurable outcomes that define success"],
    "estimated_complexity": "simple/moderate/complex",
    "estimated_total_effort": "Total time estimate",
    
    "clarification_questions": [
        {
            "id": "q1",
            "question": "Specific probing question based on gaps identified",
            "type": "choice/boolean/text",
            "options": ["Option A", "Option B", "Option C"],
            "default": "Option A",
            "priority": "high/medium/low",
            "reason": "Why this question matters"
        }
    ]
}

## CRITICAL RULES

1. "Instructional Designer" MUST be in domain_skills for ALL domains
2. domain_capabilities must be UNIQUE keys specific to the detected domain
3. EVERY step must have sub_steps (at least 2-3 detailed sub-tasks)
4. EVERY step must have validation_criteria (how to verify completion)
5. Include 5-6 steps for efficient execution planning (optimized for speed)
6. Generate 2-3 SMART clarification questions that probe gaps in the request (optimized for speed)
7. Questions should be contextual and reveal hidden requirements
8. Include risk analysis and mitigation strategies
9. Consider alternative approaches before selecting strategy

## QUESTION TYPES

- **Scope clarifiers**: "Should this cover X or just Y?"
- **Depth probers**: "How detailed should the Z section be?"
- **Constraint discoverers**: "Are there specific time/resource limits?"
- **Preference elicitors**: "Do you prefer approach A (faster) or B (more thorough)?"
- **Assumption validators**: "I'm assuming X - is this correct?"

Be THOROUGH and ANALYTICAL. This plan guides the entire generation process."""

    @property
    def name(self) -> AgentName:
        return AgentName.PREACT
    
    def _detect_domain(self, query: str) -> str:
        """
        Detect the domain from user query using keyword matching.
        Returns the most relevant domain based on keyword frequency.
        """
        query_lower = query.lower()
        domain_scores = {}
        
        for domain, keywords in DOMAIN_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            # Return domain with highest score
            return max(domain_scores, key=domain_scores.get)
        
        return "default"
    
    def _get_domain_skills(self, domain: str) -> List[str]:
        """
        Get skills for a domain. Always includes 'Instructional Designer'.
        """
        base_skills = DOMAIN_SKILLS.get(domain, DOMAIN_SKILLS["default"])
        skills = ["Instructional Designer"] + base_skills
        return list(dict.fromkeys(skills))  # Remove duplicates while preserving order
    
    def _get_domain_capabilities(self, domain: str) -> List[str]:
        """
        Get unique capability keys for a domain.
        """
        return DOMAIN_CAPABILITIES.get(domain, DOMAIN_CAPABILITIES["default"])
    
    # Analysis phases for intensive planning
    ANALYSIS_PHASES = {
        "context": "Analyze context, audience, and stakeholders",
        "requirements": "Extract explicit and implicit requirements",
        "constraints": "Identify limitations, risks, and dependencies",
        "strategy": "Evaluate approaches and select optimal strategy"
    }
    
    async def _perform_deep_analysis(
        self, 
        context: AgentContext, 
        domain: str,
        domain_context: str = ""
    ) -> Dict[str, Any]:
        """
        Perform intensive pre-planning analysis before creating the execution plan.
        Uses domain-specific deep dive focus areas for thorough analysis.
        Returns structured analysis data for plan generation.
        """
        # Get domain-specific focus areas
        deep_dive_info = DOMAIN_DEEP_DIVE.get(domain, DOMAIN_DEEP_DIVE["default"])
        focus_areas = deep_dive_info.get("focus_areas", [])
        key_questions = deep_dive_info.get("key_questions", [])
        success_metrics = deep_dive_info.get("success_metrics", [])
        
        analysis_prompt = f"""Perform INTENSIVE domain-specific analysis for this request. Output ONLY valid JSON.

## REQUEST
Domain: {domain}
Query: {context.query}

## CONTEXT
{domain_context if domain_context else "No additional context available."}

## DOMAIN-SPECIFIC FOCUS AREAS FOR {domain.upper()}
Consider these critical aspects in your analysis:
{chr(10).join(['- ' + fa for fa in focus_areas])}

## KEY DOMAIN QUESTIONS TO ANSWER
{chr(10).join(['- ' + q for q in key_questions])}

## SUGGESTED SUCCESS METRICS FOR THIS DOMAIN
{chr(10).join(['- ' + m for m in success_metrics])}

## ANALYSIS REQUIRED

Analyze thoroughly and output this JSON structure:
{{
    "audience": {{
        "primary": "Main target audience",
        "skill_level": "beginner/intermediate/advanced/mixed",
        "prerequisites": ["Required knowledge item 1", "Required knowledge item 2"],
        "goals": ["What they want to achieve"]
    }},
    "stakeholders": ["Stakeholder 1", "Stakeholder 2"],
    "context_of_use": "When/where/how this will be used",
    "motivation": "Underlying reason for this request",
    "requirements": {{
        "explicit": ["Directly stated requirement 1", "Requirement 2"],
        "implicit": ["Inferred requirement 1", "Inferred requirement 2"],
        "out_of_scope": ["What this does NOT include"]
    }},
    "risks_and_assumptions": {{
        "assumptions": ["Assumption 1", "Assumption 2"],
        "risks": ["Potential issue 1", "Challenge 2"],
        "mitigations": ["How to address risk 1", "Mitigation 2"]
    }},
    "strategy": {{
        "alternatives": [
            {{"approach": "Option A", "pros": ["Pro 1"], "cons": ["Con 1"]}},
            {{"approach": "Option B", "pros": ["Pro 1"], "cons": ["Con 1"]}}
        ],
        "recommended": "The best approach",
        "rationale": "Why this approach is best"
    }},
    "complexity_factors": ["Factor 1", "Factor 2"],
    "estimated_effort": "30min/1hr/2hr/4hr+"
}}

Output ONLY the JSON, no other text."""

        # Generate analysis (aggressively optimized for speed: lower tokens, faster response)
        analysis_response = ""
        async for chunk in self.llm.generate_stream(
            prompt=analysis_prompt,
            system_prompt="You are an expert analyst. Output concise valid JSON only. Be brief but thorough.",
            temperature=0.0,  # Set to 0 for fastest, most deterministic response
            max_tokens=600   # Further reduced from 800 for speed
        ):
            analysis_response += chunk
        
        # Parse the analysis
        try:
            json_match = re.search(r'\{[\s\S]*\}', analysis_response)
            if json_match:
                analysis_data = json.loads(json_match.group())
                return analysis_data
        except json.JSONDecodeError:
            pass
        
        # Return default analysis structure if parsing fails
        return {
            "audience": {
                "primary": "General users",
                "skill_level": "intermediate",
                "prerequisites": [],
                "goals": ["Complete the requested task"]
            },
            "stakeholders": ["Primary user"],
            "context_of_use": "Standard use case",
            "motivation": "User needs assistance with this task",
            "requirements": {
                "explicit": [context.query],
                "implicit": ["Quality output", "Accurate information"],
                "out_of_scope": []
            },
            "risks_and_assumptions": {
                "assumptions": ["User has basic domain knowledge"],
                "risks": ["Requirements may need clarification"],
                "mitigations": ["Ask clarifying questions"]
            },
            "strategy": {
                "alternatives": [],
                "recommended": "Step-by-step approach",
                "rationale": "Systematic execution ensures quality"
            },
            "complexity_factors": ["Task scope", "Domain complexity"],
            "estimated_effort": "1hr"
        }
    
    async def run(self, context: AgentContext) -> AsyncGenerator[AgentEvent, None]:
        """
        Execute PreAct reasoning - create a thinking plan before acting.
        Like Cursor's Plan Mode - THINK before executing.
        """
        yield self.create_event(
            AgentEventType.STATUS,
            "🧠 PreAct: Analyzing your request (Think Before Acting)..."
        )
        
        # Step 1: Detect domain from query
        detected_domain = self._detect_domain(context.query)
        domain_skills = self._get_domain_skills(detected_domain)
        domain_capabilities = self._get_domain_capabilities(detected_domain)
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"🎯 Domain Detection:\n"
            f"• Detected Domain: {detected_domain}\n"
            f"• Skills: {', '.join(domain_skills[:3])}...\n"
            f"• Capabilities: {', '.join(domain_capabilities[:3])}..."
        )
        
        # Store detected domain in context
        context.metadata["detected_domain"] = detected_domain
        context.metadata["domain_skills"] = domain_skills
        context.metadata["domain_capabilities"] = domain_capabilities
        
        # Use detected domain if context.domain is generic
        effective_domain = detected_domain if context.domain in ["default", "general", ""] else context.domain
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"Reading request: \"{context.query}\"\nEffective Domain: {effective_domain}"
        )
        
        # Step 2: Gather any relevant context
        domain_context = ""
        try:
            rag_results = await self.rag.search(
                query=context.query,
                domain=effective_domain,
                n_results=3
            )
            if rag_results:
                domain_context = "\n".join([f"• {r.content[:200]}" for r in rag_results])
                yield self.create_event(
                    AgentEventType.RAG_RESULT,
                    f"Found relevant context:\n{domain_context[:400]}...",
                    {"sources": [r.source for r in rag_results]}
                )
        except Exception as e:
            yield self.create_event(
                AgentEventType.THOUGHT,
                f"Proceeding without additional context: {str(e)[:100]}"
            )
        
        # Step 3: Perform DEEP ANALYSIS before planning (with timeout protection)
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"🔍 Phase 1-4: Performing deep analysis (audience, requirements, risks, strategy)..."
        )
        
        # Add timeout for deep analysis (20 seconds max)
        try:
            deep_analysis = await asyncio.wait_for(
                self._perform_deep_analysis(context, effective_domain, domain_context),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            # Use default analysis if deep analysis times out
            yield self.create_event(
                AgentEventType.THOUGHT,
                "⚠️ Deep analysis timed out, using default analysis structure..."
            )
            deep_analysis = {
                "audience": {"primary": "General users", "skill_level": "intermediate", "prerequisites": [], "goals": ["Complete the requested task"]},
                "stakeholders": ["Primary user"],
                "context_of_use": "Standard use case",
                "motivation": "User needs assistance with this task",
                "requirements": {"explicit": [context.query], "implicit": ["Quality output"], "out_of_scope": []},
                "risks_and_assumptions": {"assumptions": ["User has basic domain knowledge"], "risks": ["Requirements may need clarification"], "mitigations": ["Ask clarifying questions"]},
                "strategy": {"alternatives": [], "recommended": "Step-by-step approach", "rationale": "Systematic execution ensures quality"},
                "complexity_factors": ["Task scope"],
                "estimated_effort": "1hr"
            }
        
        # Store analysis in context
        context.metadata["deep_analysis"] = deep_analysis
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"📊 Analysis Complete:\n"
            f"• Audience: {deep_analysis.get('audience', {}).get('primary', 'General')}\n"
            f"• Skill Level: {deep_analysis.get('audience', {}).get('skill_level', 'intermediate')}\n"
            f"• Risks Identified: {len(deep_analysis.get('risks_and_assumptions', {}).get('risks', []))}\n"
            f"• Strategy: {deep_analysis.get('strategy', {}).get('recommended', 'Step-by-step')[:50]}..."
        )
        
        # Step 4: Generate the reasoning plan with domain-specific info AND deep analysis
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"📝 Creating intensive execution plan for {effective_domain} domain..."
        )
        
        planning_prompt = self._build_planning_prompt(
            context, 
            domain_context,
            detected_domain=detected_domain,
            domain_skills=domain_skills,
            domain_capabilities=domain_capabilities,
            deep_analysis=deep_analysis
        )
        
        full_response = ""
        # Optimized: Limit planning to 2000 tokens max for faster planning
        # Reduced temperature for faster, more deterministic responses
        async for chunk in self.llm.generate_stream(
            prompt=planning_prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.3,  # Reduced from 0.7 for faster responses
            max_tokens=2000  # Reduced from 3000 for speed
        ):
            full_response += chunk
            if len(full_response) % 200 == 0:
                yield self.create_event(
                    AgentEventType.THOUGHT,
                    f"Planning... ({len(full_response)} chars)"
                )
        
        # Step 4: Parse the plan
        yield self.create_event(
            AgentEventType.THOUGHT,
            "Organizing my reasoning plan..."
        )
        
        reasoning_plan = self._parse_reasoning_plan(full_response, context)
        
        # Store in context
        context.metadata["reasoning_plan"] = reasoning_plan.to_dict()
        
        # Step 5: Emit the structured plan
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"📋 Task Understanding:\n{reasoning_plan.task_understanding}"
        )
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"🎯 Approach:\n{reasoning_plan.approach}"
        )
        
        # Emit each step
        for step in reasoning_plan.steps:
            yield self.create_event(
                AgentEventType.ACTION,
                f"Step {step.step_number}: {step.title}",
                {
                    "step": step.to_dict(),
                    "event_type": "plan_step"
                }
            )
        
        # Emit constraints
        if reasoning_plan.constraints:
            yield self.create_event(
                AgentEventType.THOUGHT,
                "⚠️ Constraints:\n" + "\n".join([f"• {c}" for c in reasoning_plan.constraints])
            )
        
        # Emit success criteria
        if reasoning_plan.success_criteria:
            yield self.create_event(
                AgentEventType.THOUGHT,
                "✅ Success Criteria:\n" + "\n".join([f"• {c}" for c in reasoning_plan.success_criteria])
            )
        
        # Generate Mermaid diagram
        mermaid = self._generate_mermaid(reasoning_plan)
        
        # Create the complete plan event
        plan_summary = self._format_plan_summary(reasoning_plan)
        
        yield self.create_event(
            AgentEventType.PLAN,
            plan_summary,
            {
                "reasoning_plan": reasoning_plan.to_dict(),
                "mermaid_diagram": mermaid,
                "step_count": len(reasoning_plan.steps),
                "complexity": reasoning_plan.estimated_complexity,
                "requires_approval": True,
                "detected_domain": reasoning_plan.detected_domain,
                "domain_skills": reasoning_plan.domain_skills,
                "domain_capabilities": reasoning_plan.domain_capabilities,
                "template_id": reasoning_plan.template_id,
                "includes_instructional_designer": "Instructional Designer" in reasoning_plan.domain_skills
            }
        )
        
        # Create MasterPlan for compatibility
        context.master_plan = MasterPlan(
            title=reasoning_plan.title,
            domain=context.domain,
            total_scenes=len(reasoning_plan.steps),
            world_setting=reasoning_plan.task_understanding,
            characters=[],
            visual_style=reasoning_plan.approach,
            camera_rules=", ".join(reasoning_plan.constraints),
            tone=reasoning_plan.estimated_complexity,
            scene_outline=[f"Step {s.step_number}: {s.title}" for s in reasoning_plan.steps]
        )
        
        # Save to memory
        await self.tme.add_memory(
            session_id=context.session_id,
            content=f"Plan: {reasoning_plan.title} - {reasoning_plan.approach}",
            memory_type="plan",
            tags=["preact", "reasoning", context.domain]
        )
        
        yield self.create_event(
            AgentEventType.MEMORY_UPDATE,
            "Saved reasoning plan to memory",
            {"memory_type": "plan"}
        )
        
        yield self.create_event(
            AgentEventType.COMPLETE,
            f"✅ Reasoning plan ready!\n\n"
            f"🎯 Domain: {reasoning_plan.detected_domain}\n"
            f"📋 {len(reasoning_plan.steps)} steps planned\n"
            f"👥 {len(reasoning_plan.domain_skills)} skills (Instructional Designer: ✅)\n"
            f"🔧 {len(reasoning_plan.domain_capabilities)} capability keys\n"
            f"⚡ Complexity: {reasoning_plan.estimated_complexity}\n\n"
            f"ReAct will now execute this plan. ReFlect will validate.",
            {
                "requires_approval": True,
                "step_count": len(reasoning_plan.steps),
                "complexity": reasoning_plan.estimated_complexity,
                "detected_domain": reasoning_plan.detected_domain,
                "template_id": reasoning_plan.template_id,
                "skills_count": len(reasoning_plan.domain_skills),
                "capabilities_count": len(reasoning_plan.domain_capabilities)
            }
        )
    
    async def refine_plan(
        self,
        context: AgentContext,
        original_plan: Dict[str, Any],
        user_responses: Dict[str, Any],
        chat_message: str = "",
        chat_history: List[Dict] = None
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Refine an existing plan based on user feedback and clarification responses.
        
        Args:
            context: Agent context with session info
            original_plan: The original reasoning plan dict
            user_responses: User's responses to clarification questions
            chat_message: Additional user message for refinement
            chat_history: Previous chat messages for context
        """
        chat_history = chat_history or []
        
        yield self.create_event(
            AgentEventType.STATUS,
            "🔄 Refining plan based on your feedback..."
        )
        
        # Build refinement prompt
        refinement_prompt = self._build_refinement_prompt(
            context, original_plan, user_responses, chat_message, chat_history
        )
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"Processing your feedback:\n"
            f"• Clarification responses: {len(user_responses)}\n"
            f"• Additional instructions: {len(chat_message)} chars\n"
            f"• Chat history: {len(chat_history)} messages"
        )
        
        # Generate refined plan
        full_response = ""
        async for chunk in self.llm.generate_stream(
            prompt=refinement_prompt,
            system_prompt=self.REFINE_SYSTEM_PROMPT,
            temperature=0.7
        ):
            full_response += chunk
        
        # Parse the refined plan
        reasoning_plan = self._parse_reasoning_plan(full_response, context)
        
        # Add chat message to history
        if chat_message:
            reasoning_plan.chat_history = chat_history + [
                {"role": "user", "content": chat_message},
                {"role": "assistant", "content": f"Updated plan: {reasoning_plan.title}"}
            ]
        else:
            reasoning_plan.chat_history = chat_history
        
        # Store in context
        context.metadata["reasoning_plan"] = reasoning_plan.to_dict()
        
        # Generate Mermaid diagram
        mermaid = self._generate_mermaid(reasoning_plan)
        
        # Emit the refined plan
        plan_summary = self._format_plan_summary(reasoning_plan)
        
        yield self.create_event(
            AgentEventType.PLAN,
            plan_summary,
            {
                "reasoning_plan": reasoning_plan.to_dict(),
                "mermaid_diagram": mermaid,
                "step_count": len(reasoning_plan.steps),
                "complexity": reasoning_plan.estimated_complexity,
                "requires_approval": True,
                "detected_domain": reasoning_plan.detected_domain,
                "is_refined": True,
                "refinement_context": {
                    "user_responses": user_responses,
                    "chat_message": chat_message
                }
            }
        )
        
        yield self.create_event(
            AgentEventType.COMPLETE,
            f"✅ Plan refined!\n\n"
            f"📋 {len(reasoning_plan.steps)} steps\n"
            f"🔄 Updated based on your feedback",
            {
                "is_refined": True,
                "step_count": len(reasoning_plan.steps)
            }
        )
    
    REFINE_SYSTEM_PROMPT = """You are PreAct, the THINKER component of ThinkerLLM.

You are REFINING an existing plan based on user feedback. Your job is to:
1. Incorporate the user's clarification responses
2. Adjust the plan based on their additional instructions
3. Keep the same JSON structure
4. Update steps, approach, and constraints as needed

Output the REFINED plan in the same JSON format as before. Make sure to:
- Address all user feedback
- Keep clarification_questions that are still relevant
- Update task_understanding if the user provided more context
- Adjust steps to match the refined requirements"""
    
    def _build_refinement_prompt(
        self,
        context: AgentContext,
        original_plan: Dict[str, Any],
        user_responses: Dict[str, Any],
        chat_message: str,
        chat_history: List[Dict]
    ) -> str:
        """Build prompt for plan refinement."""
        # Format user responses
        responses_text = ""
        for q_id, response in user_responses.items():
            responses_text += f"- {q_id}: {response}\n"
        
        # Format chat history
        history_text = ""
        for msg in chat_history[-5:]:  # Last 5 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_text += f"{role.title()}: {content}\n"
        
        return f"""## ORIGINAL PLAN
{json.dumps(original_plan, indent=2)}

## USER CLARIFICATION RESPONSES
{responses_text if responses_text else "No responses provided"}

## ADDITIONAL USER INSTRUCTIONS
{chat_message if chat_message else "No additional instructions"}

## CHAT HISTORY
{history_text if history_text else "No previous chat"}

## YOUR TASK
Refine the plan above based on the user's feedback. Output the complete refined plan in JSON format.

Key changes to incorporate:
- Adjust approach based on user preferences
- Update steps to match clarified requirements
- Keep the plan actionable and specific
- Generate new clarification questions if needed"""
    
    def _build_planning_prompt(
        self, 
        context: AgentContext, 
        domain_context: str,
        detected_domain: str = "default",
        domain_skills: List[str] = None,
        domain_capabilities: List[str] = None,
        deep_analysis: Dict[str, Any] = None
    ) -> str:
        """Build the prompt for generating the reasoning plan with domain-specific info and deep analysis."""
        domain_skills = domain_skills or ["Instructional Designer"]
        domain_capabilities = domain_capabilities or []
        deep_analysis = deep_analysis or {}
        
        # Format deep analysis for prompt
        audience_info = deep_analysis.get("audience", {})
        requirements_info = deep_analysis.get("requirements", {})
        risks_info = deep_analysis.get("risks_and_assumptions", {})
        strategy_info = deep_analysis.get("strategy", {})
        
        return f"""## USER REQUEST

**Domain:** {context.domain}
**Detected Domain:** {detected_domain}
**Request:** {context.query}

## DEEP ANALYSIS (Pre-computed)

### Audience Analysis
- **Primary Audience:** {audience_info.get('primary', 'General users')}
- **Skill Level:** {audience_info.get('skill_level', 'intermediate')}
- **Prerequisites:** {json.dumps(audience_info.get('prerequisites', []))}
- **Goals:** {json.dumps(audience_info.get('goals', []))}

### Stakeholders
{json.dumps(deep_analysis.get('stakeholders', ['Primary user']))}

### Context of Use
{deep_analysis.get('context_of_use', 'Standard use case')}

### Motivation
{deep_analysis.get('motivation', 'User needs assistance')}

### Requirements Extracted
- **Explicit:** {json.dumps(requirements_info.get('explicit', []))}
- **Implicit:** {json.dumps(requirements_info.get('implicit', []))}
- **Out of Scope:** {json.dumps(requirements_info.get('out_of_scope', []))}

### Risks & Assumptions
- **Assumptions:** {json.dumps(risks_info.get('assumptions', []))}
- **Risks:** {json.dumps(risks_info.get('risks', []))}
- **Mitigations:** {json.dumps(risks_info.get('mitigations', []))}

### Strategy
- **Alternatives Considered:** {json.dumps(strategy_info.get('alternatives', []))}
- **Recommended Approach:** {strategy_info.get('recommended', 'Step-by-step')}
- **Rationale:** {strategy_info.get('rationale', 'Best for quality output')}

## DOMAIN-SPECIFIC INFORMATION

**Required Skills (include these in your plan):**
{json.dumps(domain_skills, indent=2)}

**Suggested Capability Keys (use as reference for unique keys):**
{json.dumps(domain_capabilities, indent=2)}

## RELEVANT CONTEXT
{domain_context if domain_context else "No additional context available."}

## YOUR TASK

Using the DEEP ANALYSIS above, create an INTENSIVE execution plan.

CRITICAL REQUIREMENTS:
1. "Instructional Designer" MUST be in your domain_skills list
2. Generate UNIQUE capability keys specific to {detected_domain} domain
3. EVERY step must have:
   - 2-3 detailed sub_steps
   - estimated_effort (5min/15min/30min/1hr/2hr+)
   - validation_criteria (how to verify completion)
   - tools_needed (GENERATE, SEARCH, ANALYZE)
   - priority (critical/important/optional)
4. Include 5-8 comprehensive steps
5. Generate 3-5 CONTEXTUAL clarification questions based on gaps in the analysis
6. Questions must have priority (high/medium/low) and reason (why it matters)

Each step should:
- Address specific requirements from the analysis
- Account for identified risks
- Target the correct audience level
- Be executable by the ReAct agent

Create your INTENSIVE reasoning plan in the JSON format specified."""
    
    def _parse_reasoning_plan(self, response: str, context: AgentContext) -> ReasoningPlan:
        """Parse the LLM response into a ReasoningPlan with all enhanced fields."""
        # Get domain info from context metadata
        detected_domain = context.metadata.get("detected_domain", "default")
        default_skills = context.metadata.get("domain_skills", ["Instructional Designer"])
        default_capabilities = context.metadata.get("domain_capabilities", [])
        deep_analysis = context.metadata.get("deep_analysis", {})
        
        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        
        if json_match:
            try:
                plan_data = json.loads(json_match.group())
                
                # Parse steps with enhanced fields
                steps = []
                for i, step_data in enumerate(plan_data.get("steps", [])):
                    steps.append(ReasoningStep(
                        step_number=step_data.get("step_number", i + 1),
                        title=step_data.get("title", f"Step {i + 1}"),
                        description=step_data.get("description", ""),
                        expected_output=step_data.get("expected_output", ""),
                        dependencies=step_data.get("dependencies", []),
                        # Enhanced fields
                        sub_steps=step_data.get("sub_steps", []),
                        estimated_effort=step_data.get("estimated_effort", "15min"),
                        validation_criteria=step_data.get("validation_criteria", []),
                        tools_needed=step_data.get("tools_needed", ["GENERATE"]),
                        priority=step_data.get("priority", "important")
                    ))
                
                # Extract domain-specific fields from LLM response or use defaults
                domain_skills = plan_data.get("domain_skills", default_skills)
                # Ensure Instructional Designer is always included
                if "Instructional Designer" not in domain_skills:
                    domain_skills = ["Instructional Designer"] + domain_skills
                
                domain_capabilities = plan_data.get("domain_capabilities", default_capabilities)
                
                # Parse clarification questions with enhanced fields
                clarification_questions = []
                for q_data in plan_data.get("clarification_questions", []):
                    clarification_questions.append(ClarificationQuestion(
                        id=q_data.get("id", f"q{len(clarification_questions)+1}"),
                        question=q_data.get("question", ""),
                        question_type=q_data.get("type", "boolean"),
                        options=q_data.get("options", []),
                        default=q_data.get("default"),
                        priority=q_data.get("priority", "medium"),
                        reason=q_data.get("reason", "Helps clarify requirements")
                    ))
                
                # Generate contextual questions if none provided, using deep analysis
                if not clarification_questions:
                    clarification_questions = self._generate_contextual_questions(
                        context, detected_domain, deep_analysis
                    )
                
                # Extract deep analysis fields from response or use pre-computed analysis
                response_deep_analysis = plan_data.get("deep_analysis", deep_analysis)
                response_requirements = plan_data.get("requirements", deep_analysis.get("requirements", {}))
                response_risks = plan_data.get("risks_and_assumptions", deep_analysis.get("risks_and_assumptions", {}))
                response_strategy = plan_data.get("strategy", deep_analysis.get("strategy", {}))
                
                return ReasoningPlan(
                    title=plan_data.get("title", f"{context.domain} Task"),
                    task_understanding=plan_data.get("task_understanding", context.query),
                    approach=plan_data.get("approach", "Step-by-step execution"),
                    steps=steps,
                    constraints=plan_data.get("constraints", []),
                    success_criteria=plan_data.get("success_criteria", []),
                    estimated_complexity=plan_data.get("estimated_complexity", "moderate"),
                    detected_domain=plan_data.get("detected_domain", detected_domain),
                    domain_skills=domain_skills,
                    domain_capabilities=domain_capabilities,
                    clarification_questions=clarification_questions,
                    # Enhanced deep analysis fields
                    deep_analysis=response_deep_analysis,
                    requirements=response_requirements,
                    risks_and_assumptions=response_risks,
                    strategy=response_strategy,
                    estimated_total_effort=plan_data.get("estimated_total_effort")
                )
            except json.JSONDecodeError:
                pass
        
        # Fallback: Create a default plan with deep analysis
        return self._create_default_plan(context, response)
    
    def _generate_contextual_questions(
        self, 
        context: AgentContext, 
        domain: str,
        deep_analysis: Dict[str, Any] = None
    ) -> List[ClarificationQuestion]:
        """
        Generate SMART contextual clarification questions based on:
        - Gaps identified in the deep analysis
        - Domain-specific requirements
        - Query ambiguities
        """
        questions = []
        query_lower = context.query.lower()
        deep_analysis = deep_analysis or {}
        
        # Extract analysis data
        audience = deep_analysis.get("audience", {})
        requirements = deep_analysis.get("requirements", {})
        risks = deep_analysis.get("risks_and_assumptions", {})
        
        # ============ SCOPE CLARIFIERS ============
        # Check for ambiguous scope in query
        scope_indicators = ["and", "or", "also", "including", "such as", "like"]
        if any(ind in query_lower for ind in scope_indicators):
            questions.append(ClarificationQuestion(
                id="q_scope",
                question="I noticed multiple elements in your request. Should I cover all of them equally, or prioritize specific aspects?",
                question_type="choice",
                options=["Cover all equally", "Focus on the first/main topic", "Let me specify priorities"],
                default="Cover all equally",
                priority="high",
                reason="Clarifies scope to avoid scope creep or missing key elements"
            ))
        
        # ============ AUDIENCE PROBERS ============
        # If audience skill level is unclear
        if not audience.get("skill_level") or audience.get("skill_level") == "intermediate":
            questions.append(ClarificationQuestion(
                id="q_audience_level",
                question="What is the expertise level of your target audience?",
                question_type="choice",
                options=["Complete beginners (no prior knowledge)", "Some familiarity (basic concepts known)", "Intermediate (comfortable with fundamentals)", "Advanced (looking for deep insights)"],
                default="Some familiarity (basic concepts known)",
                priority="high",
                reason="Determines depth of explanations and assumed prerequisites"
            ))
        
        # ============ DEPTH PROBERS ============
        if "overview" not in query_lower and "summary" not in query_lower:
            questions.append(ClarificationQuestion(
                id="q_depth",
                question="How comprehensive should the output be?",
                question_type="choice",
                options=["Quick overview (key points only)", "Standard depth (balanced)", "Comprehensive (thorough coverage)", "Expert-level (maximum detail)"],
                default="Standard depth (balanced)",
                priority="medium",
                reason="Balances completeness against time and length"
            ))
        
        # ============ DOMAIN-SPECIFIC QUESTIONS ============
        
        # Education domain
        if domain == "education" or any(w in query_lower for w in ["course", "lesson", "tutorial", "training", "curriculum"]):
            questions.append(ClarificationQuestion(
                id="q_learning_style",
                question="What learning approach works best for your audience?",
                question_type="choice",
                options=["Theory first, then practice", "Learn by doing (hands-on)", "Case study based", "Mixed approach with examples"],
                default="Mixed approach with examples",
                priority="high",
                reason="Shapes content structure and engagement strategy"
            ))
            questions.append(ClarificationQuestion(
                id="q_assessment",
                question="Should I include assessments or practice exercises?",
                question_type="choice",
                options=["Yes, with quizzes after each section", "Yes, exercises only (no quizzes)", "Just a final assessment", "No assessments needed"],
                default="Yes, with quizzes after each section",
                priority="medium",
                reason="Determines if learner validation is needed"
            ))
        
        # Software/Technical domain
        elif domain == "software" or any(w in query_lower for w in ["code", "programming", "api", "development", "technical"]):
            questions.append(ClarificationQuestion(
                id="q_tech_stack",
                question="Are there specific technologies or versions I should target?",
                question_type="text",
                default="Latest stable versions",
                priority="high",
                reason="Ensures code examples and recommendations are compatible"
            ))
            questions.append(ClarificationQuestion(
                id="q_production_ready",
                question="Should this be production-ready or educational/prototype quality?",
                question_type="choice",
                options=["Production-ready (error handling, security, tests)", "Educational (clear but simplified)", "Prototype (quick and functional)"],
                default="Educational (clear but simplified)",
                priority="medium",
                reason="Affects code complexity and completeness"
            ))
        
        # Business/Analysis domain  
        elif domain in ["finance", "sales", "marketing", "hr"] or any(w in query_lower for w in ["analysis", "strategy", "plan", "report"]):
            questions.append(ClarificationQuestion(
                id="q_stakeholders",
                question="Who is the primary audience for this output?",
                question_type="choice",
                options=["Executive leadership (high-level)", "Department managers (tactical)", "Team members (operational)", "External stakeholders (clients/partners)"],
                default="Department managers (tactical)",
                priority="high",
                reason="Adjusts language, detail level, and focus areas"
            ))
            questions.append(ClarificationQuestion(
                id="q_data_support",
                question="Should I include data, metrics, or examples to support recommendations?",
                question_type="choice",
                options=["Yes, with specific numbers/data", "Yes, with general examples", "Just recommendations, no data needed"],
                default="Yes, with general examples",
                priority="medium",
                reason="Determines evidence requirements"
            ))
        
        # ============ CONSTRAINT DISCOVERERS ============
        # Check for time/resource constraints
        if len(risks.get("risks", [])) > 0:
            questions.append(ClarificationQuestion(
                id="q_constraints",
                question="Are there any specific constraints I should know about?",
                question_type="choice",
                options=["Time-sensitive (need it fast)", "Quality-focused (take time for best result)", "Budget/resource limited", "No specific constraints"],
                default="Quality-focused (take time for best result)",
                priority="medium",
                reason="Balances speed vs thoroughness"
            ))
        
        # ============ ASSUMPTION VALIDATORS ============
        assumptions = risks.get("assumptions", [])
        if assumptions and len(assumptions) > 0:
            # Create a question to validate the top assumption
            top_assumption = assumptions[0] if assumptions else "standard approach applies"
            questions.append(ClarificationQuestion(
                id="q_assumption_check",
                question=f"I'm assuming: '{top_assumption}'. Is this correct?",
                question_type="boolean",
                default="yes",
                priority="medium",
                reason="Validates key assumptions before proceeding"
            ))
        
        # ============ FORMAT PREFERENCE ============
        questions.append(ClarificationQuestion(
            id="q_format",
            question="What format works best for your needs?",
            question_type="choice",
            options=["Structured document with sections", "Step-by-step guide", "Bullet points and lists", "Narrative/conversational style"],
            default="Structured document with sections",
            priority="low",
            reason="Ensures output matches expected presentation style"
        ))
        
        # Limit to 5 most important questions
        questions.sort(key=lambda q: {"high": 0, "medium": 1, "low": 2}.get(q.priority, 1))
        return questions[:5]
    
    def _generate_default_questions(self, context: AgentContext, domain: str) -> List[ClarificationQuestion]:
        """Backward compatibility wrapper - calls contextual questions with no analysis."""
        return self._generate_contextual_questions(context, domain, {})
    
    def _create_default_plan(self, context: AgentContext, raw_response: str) -> ReasoningPlan:
        """Create a comprehensive default plan when parsing fails."""
        # Get domain info from context metadata
        detected_domain = context.metadata.get("detected_domain", "default")
        domain_skills = context.metadata.get("domain_skills", self._get_domain_skills(detected_domain))
        domain_capabilities = context.metadata.get("domain_capabilities", self._get_domain_capabilities(detected_domain))
        deep_analysis = context.metadata.get("deep_analysis", {})
        
        # Ensure Instructional Designer is always included
        if "Instructional Designer" not in domain_skills:
            domain_skills = ["Instructional Designer"] + domain_skills
        
        # Try to extract steps from the response
        steps = []
        step_patterns = [
            r"(?:Step\s*)?(\d+)[.:\s]+(.+?)(?=(?:Step\s*)?\d+[.:]|$)",
            r"(\d+)\)\s*(.+?)(?=\d+\)|$)"
        ]
        
        for pattern in step_patterns:
            matches = re.findall(pattern, raw_response, re.IGNORECASE | re.DOTALL)
            if matches:
                for num, content in matches[:8]:
                    steps.append(ReasoningStep(
                        step_number=int(num),
                        title=content.strip()[:50],
                        description=content.strip(),
                        expected_output="Completed step output",
                        dependencies=[],
                        sub_steps=["Analyze requirements", "Execute task", "Verify output"],
                        estimated_effort="15min",
                        validation_criteria=["Output matches requirements"],
                        tools_needed=["GENERATE"],
                        priority="important"
                    ))
                break
        
        # If no steps found, create comprehensive default steps
        if not steps:
            steps = [
                ReasoningStep(
                    step_number=1,
                    title="Deep Analysis & Context Gathering",
                    description=f"Thoroughly analyze: {context.query} in {detected_domain} domain",
                    expected_output="Complete understanding of requirements, audience, and constraints",
                    dependencies=[],
                    sub_steps=[
                        "Identify target audience and skill level",
                        "Extract explicit and implicit requirements",
                        "Identify constraints and dependencies",
                        "Document assumptions"
                    ],
                    estimated_effort="15min",
                    validation_criteria=["All requirements documented", "Audience clearly defined"],
                    tools_needed=["ANALYZE", "SEARCH"],
                    priority="critical"
                ),
                ReasoningStep(
                    step_number=2,
                    title="Strategy Selection & Planning",
                    description=f"Select optimal approach and plan execution for {detected_domain} domain",
                    expected_output="Clear execution strategy with alternatives considered",
                    dependencies=[1],
                    sub_steps=[
                        "Evaluate alternative approaches",
                        "Select best strategy based on requirements",
                        "Define success metrics",
                        "Plan resource allocation"
                    ],
                    estimated_effort="10min",
                    validation_criteria=["Strategy documented", "Trade-offs understood"],
                    tools_needed=["ANALYZE"],
                    priority="critical"
                ),
                ReasoningStep(
                    step_number=3,
                    title="Domain Skills Application",
                    description=f"Apply domain skills: {', '.join(domain_skills[:3])}",
                    expected_output="Domain-specific content framework",
                    dependencies=[2],
                    sub_steps=[
                        "Apply Instructional Designer principles",
                        "Incorporate domain expertise",
                        "Structure content appropriately"
                    ],
                    estimated_effort="20min",
                    validation_criteria=["Instructional design principles applied", "Content structured for audience"],
                    tools_needed=["GENERATE"],
                    priority="important"
                ),
                ReasoningStep(
                    step_number=4,
                    title="Content Generation",
                    description="Generate comprehensive content based on analysis and strategy",
                    expected_output="Complete draft content addressing all requirements",
                    dependencies=[3],
                    sub_steps=[
                        "Generate main content sections",
                        "Include examples and illustrations",
                        "Add supporting materials"
                    ],
                    estimated_effort="30min",
                    validation_criteria=["All requirements addressed", "Content is comprehensive"],
                    tools_needed=["GENERATE", "SEARCH"],
                    priority="critical"
                ),
                ReasoningStep(
                    step_number=5,
                    title="Quality Validation",
                    description="Validate output against success criteria and constraints",
                    expected_output="Validated, quality-assured deliverable",
                    dependencies=[4],
                    sub_steps=[
                        "Check against success criteria",
                        "Verify constraint compliance",
                        "Review for accuracy and completeness"
                    ],
                    estimated_effort="15min",
                    validation_criteria=["All success criteria met", "No constraint violations"],
                    tools_needed=["ANALYZE"],
                    priority="important"
                ),
                ReasoningStep(
                    step_number=6,
                    title="Final Compilation",
                    description="Compile all components into final deliverable format",
                    expected_output="Complete, polished final output",
                    dependencies=[5],
                    sub_steps=[
                        "Format output appropriately",
                        "Add finishing touches",
                        "Prepare for delivery"
                    ],
                    estimated_effort="10min",
                    validation_criteria=["Output is complete", "Format is appropriate"],
                    tools_needed=["GENERATE"],
                    priority="important"
                )
            ]
        
        # Generate contextual clarification questions
        clarification_questions = self._generate_contextual_questions(context, detected_domain, deep_analysis)
        
        return ReasoningPlan(
            title=f"{detected_domain.replace('_', ' ').title()} Intensive Plan",
            task_understanding=context.query,
            approach=f"Systematic {detected_domain} domain execution with intensive 4-phase analysis and Instructional Designer skill",
            steps=steps,
            constraints=[
                "Instructional Designer skill must be included",
                "All capability keys must be unique to this domain",
                "Follow domain-specific best practices",
                "Ensure accuracy and relevance",
                "Validate against success criteria"
            ],
            success_criteria=[
                "Request fully addressed",
                "Instructional Designer skill present",
                "All capability keys are unique",
                "Output follows required schema",
                "Quality validation passed"
            ],
            estimated_complexity="moderate",
            detected_domain=detected_domain,
            domain_skills=domain_skills,
            domain_capabilities=domain_capabilities,
            clarification_questions=clarification_questions,
            # Deep analysis fields
            deep_analysis=deep_analysis if deep_analysis else {
                "audience": {"primary": "General users", "skill_level": "intermediate", "prerequisites": [], "goals": []},
                "stakeholders": ["Primary user"],
                "context": "Standard use case",
                "motivation": "Task completion"
            },
            requirements={
                "explicit": [context.query],
                "implicit": ["Quality output", "Accurate content", "Domain relevance"],
                "out_of_scope": []
            },
            risks_and_assumptions={
                "assumptions": ["User has basic domain knowledge", "Standard requirements apply"],
                "risks": ["Requirements may need clarification", "Scope may expand"],
                "mitigations": ["Ask clarifying questions", "Validate incrementally"]
            },
            strategy={
                "alternatives_considered": [
                    {"approach": "Quick overview", "pros": ["Fast"], "cons": ["Less thorough"]},
                    {"approach": "Deep dive", "pros": ["Comprehensive"], "cons": ["Takes longer"]}
                ],
                "selected_approach": "Balanced comprehensive approach",
                "rationale": "Provides thorough coverage while remaining practical"
            }
        )
    
    def _generate_mermaid(self, plan: ReasoningPlan) -> str:
        """Generate a Mermaid diagram from the reasoning plan."""
        diagram = f"""graph TD
    subgraph Plan["📋 {plan.title}"]
        UNDERSTAND["🤔 Understanding<br/>{plan.task_understanding[:30]}..."]
"""
        
        # Add step nodes
        prev_node = "UNDERSTAND"
        for step in plan.steps:
            node_id = f"STEP{step.step_number}"
            label = f"{step.step_number}. {step.title[:25]}..."
            diagram += f'        {node_id}["{label}"]\n'
            
            if step.dependencies:
                for dep in step.dependencies:
                    diagram += f'        STEP{dep} --> {node_id}\n'
            else:
                diagram += f'        {prev_node} --> {node_id}\n'
            
            prev_node = node_id
        
        diagram += f"""        {prev_node} --> OUTPUT["✅ Final Output"]
    end
    
    style Plan fill:#f0f9ff
    style UNDERSTAND fill:#dbeafe
    style OUTPUT fill:#dcfce7
"""
        
        return diagram
    
    def _format_plan_summary(self, plan: ReasoningPlan) -> str:
        """Format the plan as a comprehensive summary with all analysis fields."""
        summary = f"""# 🧠 Intensive Reasoning Plan: {plan.title}

## 🎯 Domain & Context
**Domain:** {plan.detected_domain}
**Complexity:** {plan.estimated_complexity.upper()}
**Estimated Effort:** {plan.estimated_total_effort}
**Template ID:** {plan.template_id}

## 📋 Task Understanding
{plan.task_understanding}

## 🎯 Selected Approach
{plan.approach}
"""

        # Deep Analysis Section
        if plan.deep_analysis:
            audience = plan.deep_analysis.get("audience", {})
            summary += f"""
## 👥 Audience Analysis
- **Target:** {audience.get('primary', 'General users')}
- **Skill Level:** {audience.get('skill_level', 'intermediate')}
- **Prerequisites:** {', '.join(audience.get('prerequisites', [])) or 'None specified'}
- **Goals:** {', '.join(audience.get('goals', [])) or 'Not specified'}
"""
            if plan.deep_analysis.get("stakeholders"):
                summary += f"- **Stakeholders:** {', '.join(plan.deep_analysis.get('stakeholders', []))}\n"
        
        # Requirements Section
        if plan.requirements:
            summary += "\n## 📋 Requirements Analysis\n"
            if plan.requirements.get("explicit"):
                summary += "**Explicit Requirements:**\n"
                for r in plan.requirements.get("explicit", [])[:5]:
                    summary += f"  ✓ {r}\n"
            if plan.requirements.get("implicit"):
                summary += "**Implicit Requirements:**\n"
                for r in plan.requirements.get("implicit", [])[:3]:
                    summary += f"  ○ {r}\n"
            if plan.requirements.get("out_of_scope"):
                summary += "**Out of Scope:**\n"
                for r in plan.requirements.get("out_of_scope", [])[:3]:
                    summary += f"  ✗ {r}\n"
        
        # Risks & Assumptions
        if plan.risks_and_assumptions:
            summary += "\n## ⚠️ Risks & Assumptions\n"
            if plan.risks_and_assumptions.get("assumptions"):
                summary += "**Assumptions:**\n"
                for a in plan.risks_and_assumptions.get("assumptions", [])[:3]:
                    summary += f"  📌 {a}\n"
            if plan.risks_and_assumptions.get("risks"):
                summary += "**Risks:**\n"
                for r in plan.risks_and_assumptions.get("risks", [])[:3]:
                    summary += f"  ⚡ {r}\n"
            if plan.risks_and_assumptions.get("mitigations"):
                summary += "**Mitigations:**\n"
                for m in plan.risks_and_assumptions.get("mitigations", [])[:3]:
                    summary += f"  🛡️ {m}\n"
        
        # Strategy Section
        if plan.strategy and plan.strategy.get("alternatives_considered"):
            summary += "\n## 🎲 Strategy Analysis\n"
            for alt in plan.strategy.get("alternatives_considered", [])[:2]:
                if isinstance(alt, dict):
                    summary += f"**Alternative:** {alt.get('approach', 'N/A')}\n"
                    summary += f"  Pros: {', '.join(alt.get('pros', []))}\n"
                    summary += f"  Cons: {', '.join(alt.get('cons', []))}\n"
            if plan.strategy.get("rationale"):
                summary += f"\n**Why This Approach:** {plan.strategy.get('rationale')}\n"

        # Domain Skills
        summary += "\n## 👥 Domain Skills\n"
        for skill in plan.domain_skills:
            marker = "⭐" if skill == "Instructional Designer" else "•"
            summary += f"{marker} {skill}\n"
        
        summary += "\n## 🔧 Domain Capabilities\n"
        for cap in plan.domain_capabilities:
            summary += f"• `{cap}`\n"
        
        # Detailed Execution Steps
        summary += "\n## 📝 Execution Steps (Detailed)\n"
        
        for step in plan.steps:
            deps = f" *(depends on: {', '.join(map(str, step.dependencies))})*" if step.dependencies else ""
            priority_icon = {"critical": "🔴", "important": "🟡", "optional": "🟢"}.get(step.priority, "🟡")
            
            summary += f"""
### {priority_icon} Step {step.step_number}: {step.title}{deps}
**Effort:** {step.estimated_effort} | **Priority:** {step.priority} | **Tools:** {', '.join(step.tools_needed)}

{step.description}

"""
            # Sub-steps
            if step.sub_steps:
                summary += "**Sub-tasks:**\n"
                for i, sub in enumerate(step.sub_steps, 1):
                    summary += f"  {i}. {sub}\n"
            
            # Validation criteria
            if step.validation_criteria:
                summary += "**Validation:**\n"
                for v in step.validation_criteria:
                    summary += f"  ✓ {v}\n"
            
            summary += f"**Expected Output:** {step.expected_output}\n"
        
        # Constraints
        if plan.constraints:
            summary += "\n## 🚧 Constraints\n"
            for c in plan.constraints:
                summary += f"- {c}\n"
        
        # Success Criteria
        if plan.success_criteria:
            summary += "\n## ✅ Success Criteria\n"
            for c in plan.success_criteria:
                summary += f"- {c}\n"
        
        # Metadata
        summary += f"\n## 📊 Plan Metadata\n"
        summary += f"- **Created:** {plan.created_at}\n"
        summary += f"- **Total Steps:** {len(plan.steps)}\n"
        summary += f"- **Critical Steps:** {sum(1 for s in plan.steps if s.priority == 'critical')}\n"
        summary += f"- **Instructional Designer:** {'✅ Included' if 'Instructional Designer' in plan.domain_skills else '❌ Missing'}\n"
        summary += f"- **Analysis Depth:** Intensive (4-phase)\n"
        
        return summary
