"""
ReFlect Agent - Self-Reflection ("Evaluate → Improve → Final")

Pattern: Produce Answer → Critique → Improve → Deliver Final Output

This is the VALIDATOR component of ThinkerLLM - validating ReAct's output.

This agent:
1. Takes the output from ReACT
2. Performs self-critique
3. Validates template structure (for template generation)
4. Improves based on critique
5. Delivers polished final output

Enhanced for Template Validation:
- Validates "Instructional Designer" skill is present
- Checks for unique capability keys (no duplication)
- Validates JSON schema compliance
- Ensures required fields are present

Use when you want:
- High quality writing
- Low hallucination
- Polished final output
- Template validation

Strengths: Huge improvement in output quality
Weaknesses: Extra cost + latency (two forward passes)
"""

from typing import AsyncGenerator, Optional, Dict, Any, List
import json
import re
import uuid
from datetime import datetime

from .base import BaseAgent, AgentContext
from models.schemas import AgentEvent, AgentName, AgentEventType, Storyboard, Scene
from config import settings


class ReFlectAgent(BaseAgent):
    """
    ReFlect Agent - Self-Reflection for Quality Improvement (THE VALIDATOR)
    
    Pattern: Critique → Validate → Improve → Final
    
    1. CRITIQUE: Evaluate the current output
       - What's good?
       - What's wrong?
       - What's missing?
       - Any hallucinations?
    
    2. VALIDATE (for templates): Check template requirements
       - Is "Instructional Designer" skill present?
       - Are capability keys unique?
       - Does JSON schema comply?
       - Are required fields present?
    
    3. IMPROVE: Rewrite based on critique
       - Fix issues
       - Add missing content
       - Polish language
    
    4. FINAL: Deliver validated, improved output
    """
    
    CRITIQUE_PROMPT = """You are a critical reviewer. Evaluate this content thoroughly.

## CONTENT TO REVIEW
{content}

## ORIGINAL REQUEST
{query}

## CRITIQUE CHECKLIST
Rate each aspect (1-10) and explain:

1. ACCURACY: Is the information correct? Any hallucinations?
   Score: [1-10]
   Issues: [list any inaccuracies]

2. COMPLETENESS: Does it fully address the request?
   Score: [1-10]
   Missing: [list missing elements]

3. COHERENCE: Does it flow logically?
   Score: [1-10]
   Problems: [list flow issues]

4. QUALITY: Is it well-written and polished?
   Score: [1-10]
   Weaknesses: [list writing issues]

5. RELEVANCE: Does it stay on topic?
   Score: [1-10]
   Off-topic: [list irrelevant parts]

## OVERALL ASSESSMENT
Overall Score: [average of above]
Needs Improvement: [yes/no]
Priority Fixes: [top 3 things to fix]

Provide your critique:"""

    IMPROVE_PROMPT = """You are an expert editor. Improve this content based on the critique.

## ORIGINAL CONTENT
{content}

## CRITIQUE
{critique}

## IMPROVEMENT INSTRUCTIONS
1. Fix all accuracy issues (NO hallucinations)
2. Add any missing elements mentioned in the critique
3. Improve flow and coherence
4. Polish the writing - make it clear and professional
5. Keep what's already good
6. IMPORTANT: Output clean, well-formatted text that can be displayed to users
7. Use proper headings (## for main, ### for sub), bullet points, and paragraphs
8. Do NOT output raw JSON unless the original request specifically asked for JSON
9. Make the content actionable and useful

## IMPROVED VERSION
Rewrite the content, addressing ALL issues from the critique. Format it nicely:"""

    TEMPLATE_VALIDATION_PROMPT = """You are a template validator for ThinkerLLM. Validate this domain template.

## TEMPLATE TO VALIDATE
{template}

## DOMAIN INFORMATION
Domain: {domain}
Expected Skills: {expected_skills}
Expected Capability Keys: {expected_capabilities}

## VALIDATION CHECKLIST
Check each requirement and score (1-10):

1. INSTRUCTIONAL_DESIGNER_PRESENT: Is "Instructional Designer" in the skills array?
   Present: [yes/no]
   Score: [10 if yes, 0 if no]

2. SKILLS_COMPLETE: Are all expected domain skills present?
   Missing Skills: [list any missing]
   Score: [1-10]

3. UNIQUE_KEYS: Are all capability keys unique (not duplicated)?
   Duplicates Found: [list any duplicates]
   Score: [10 if no duplicates, lower if duplicates]

4. SCHEMA_COMPLIANCE: Does it follow the required JSON structure?
   - Has "id" (UUID v4): [yes/no]
   - Has "domain": [yes/no]
   - Has "metadata": [yes/no]
   - Has "skills" array: [yes/no]
   - Has "capabilities" object: [yes/no]
   - Has "templates" object: [yes/no]
   Schema Score: [1-10]

5. CONTENT_QUALITY: Is the template content meaningful and domain-specific?
   Score: [1-10]
   Issues: [list any quality issues]

## VALIDATION RESULT
Overall Valid: [yes/no]
Overall Score: [average of above]
Critical Issues: [list critical issues that must be fixed]
Recommended Fixes: [list recommended improvements]

Provide your validation:"""

    @property
    def name(self) -> AgentName:
        return AgentName.REFLECT
    
    def _validate_template_structure(self, template_data: Dict, context: AgentContext) -> Dict[str, Any]:
        """
        Validate template structure programmatically.
        Returns validation results with scores and issues.
        """
        validation = {
            "is_valid": True,
            "instructional_designer_present": False,
            "skills_present": [],
            "skills_missing": [],
            "has_unique_keys": True,
            "duplicate_keys": [],
            "schema_valid": True,
            "schema_issues": [],
            "overall_score": 10,
            "critical_issues": []
        }
        
        # Get expected values from context
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        expected_skills = reasoning_plan.get("domain_skills", ["Instructional Designer"])
        expected_capabilities = reasoning_plan.get("domain_capabilities", [])
        
        # Check if it's a valid dict
        if not isinstance(template_data, dict):
            validation["is_valid"] = False
            validation["critical_issues"].append("Template is not a valid dictionary")
            validation["overall_score"] = 0
            return validation
        
        # Navigate to the domain template (might be nested)
        domain_template = template_data
        if len(template_data) == 1:
            # Template might be wrapped in domain key
            domain_key = list(template_data.keys())[0]
            if isinstance(template_data[domain_key], dict):
                domain_template = template_data[domain_key]
        
        # 1. Check for Instructional Designer
        skills = domain_template.get("skills", [])
        if isinstance(skills, list):
            validation["skills_present"] = skills
            validation["instructional_designer_present"] = "Instructional Designer" in skills
            if not validation["instructional_designer_present"]:
                validation["critical_issues"].append("'Instructional Designer' skill is MISSING")
                validation["overall_score"] -= 3
        else:
            validation["schema_issues"].append("skills is not an array")
            validation["overall_score"] -= 2
        
        # Check for expected skills
        for skill in expected_skills:
            if skill not in skills:
                validation["skills_missing"].append(skill)
        
        # 2. Check for unique capability keys
        capabilities = domain_template.get("capabilities", {})
        if isinstance(capabilities, dict):
            keys = list(capabilities.keys())
            seen_keys = set()
            for key in keys:
                if key in seen_keys:
                    validation["duplicate_keys"].append(key)
                    validation["has_unique_keys"] = False
                seen_keys.add(key)
            
            if validation["duplicate_keys"]:
                validation["critical_issues"].append(f"Duplicate keys found: {validation['duplicate_keys']}")
                validation["overall_score"] -= 2
        else:
            validation["schema_issues"].append("capabilities is not an object")
            validation["overall_score"] -= 2
        
        # 3. Check schema compliance
        required_fields = ["id", "domain", "metadata", "skills", "capabilities"]
        for field in required_fields:
            if field not in domain_template:
                validation["schema_issues"].append(f"Missing required field: {field}")
                validation["schema_valid"] = False
                validation["overall_score"] -= 1
        
        # Check metadata structure
        metadata = domain_template.get("metadata", {})
        if isinstance(metadata, dict):
            if "created_at" not in metadata:
                validation["schema_issues"].append("metadata missing 'created_at'")
            if "generated_by" not in metadata:
                validation["schema_issues"].append("metadata missing 'generated_by'")
        
        # Check UUID format
        template_id = domain_template.get("id", "")
        try:
            uuid.UUID(template_id)
        except (ValueError, TypeError):
            validation["schema_issues"].append("id is not a valid UUID v4")
            validation["overall_score"] -= 1
        
        # Final validity check
        validation["is_valid"] = (
            validation["instructional_designer_present"] and
            validation["has_unique_keys"] and
            validation["schema_valid"] and
            len(validation["critical_issues"]) == 0
        )
        
        validation["overall_score"] = max(0, min(10, validation["overall_score"]))
        
        return validation
    
    async def run(self, context: AgentContext) -> AsyncGenerator[AgentEvent, None]:
        """
        Execute ReFlect: Critique → Validate → Improve → Final
        """
        yield self.create_event(
            AgentEventType.STATUS,
            "🔄 ReFlect: Starting self-reflection and validation..."
        )
        
        # Get content from ReACT
        react_output = context.metadata.get("react_output", "")
        react_scenes = context.metadata.get("react_scenes", [])
        domain_template = context.metadata.get("domain_template", {})
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        detected_domain = reasoning_plan.get("detected_domain", context.domain)
        
        if not react_output:
            yield self.create_event(
                AgentEventType.THOUGHT,
                "No content from ReACT. Nothing to reflect on."
            )
            return
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"Reviewing {len(react_output)} characters of content...\n"
            f"Domain: {detected_domain}\n"
            f"Template data available: {'Yes' if domain_template else 'No'}"
        )
        
        # ===============================
        # PHASE 0: TEMPLATE VALIDATION (if template was generated)
        # ===============================
        template_validation = None
        if domain_template:
            yield self.create_event(
                AgentEventType.STATUS,
                "🔍 Phase 0: Template Validation - Checking template structure..."
            )
            
            # Programmatic validation
            template_validation = self._validate_template_structure(domain_template, context)
            
            # Emit validation results
            yield self.create_event(
                AgentEventType.OBSERVATION,
                f"📋 Template Validation Results:\n"
                f"• Instructional Designer: {'✅ Present' if template_validation['instructional_designer_present'] else '❌ MISSING'}\n"
                f"• Unique Keys: {'✅ Yes' if template_validation['has_unique_keys'] else '❌ Duplicates found'}\n"
                f"• Schema Valid: {'✅ Yes' if template_validation['schema_valid'] else '❌ Issues found'}\n"
                f"• Overall Valid: {'✅ Yes' if template_validation['is_valid'] else '❌ No'}\n"
                f"• Validation Score: {template_validation['overall_score']}/10",
                {
                    "template_validation": template_validation,
                    "event_type": "template_validation"
                }
            )
            
            if template_validation["critical_issues"]:
                yield self.create_event(
                    AgentEventType.THOUGHT,
                    "🚨 Critical Issues:\n" + "\n".join([f"• {issue}" for issue in template_validation["critical_issues"]])
                )
            
            if template_validation["schema_issues"]:
                yield self.create_event(
                    AgentEventType.THOUGHT,
                    "⚠️ Schema Issues:\n" + "\n".join([f"• {issue}" for issue in template_validation["schema_issues"]])
                )
            
            # Store validation results
            context.metadata["template_validation"] = template_validation
        
        # ===============================
        # PHASE 1: CRITIQUE
        # ===============================
        yield self.create_event(
            AgentEventType.STATUS,
            "📝 Phase 1: Critique - Evaluating output..."
        )
        
        # Build critique prompt - include template validation context if available
        critique_context = ""
        if template_validation:
            critique_context = f"""

## TEMPLATE VALIDATION CONTEXT
The output is a domain template. Include template-specific validation:
- Domain: {detected_domain}
- Instructional Designer Present: {template_validation['instructional_designer_present']}
- Unique Keys: {template_validation['has_unique_keys']}
- Schema Valid: {template_validation['schema_valid']}
- Critical Issues: {template_validation['critical_issues']}

When critiquing, also consider:
1. Is the template content domain-specific and meaningful?
2. Are the skills appropriate for this domain?
3. Are the capability keys unique and relevant?
"""
        
        critique_prompt = self.CRITIQUE_PROMPT.format(
            content=react_output[:3000],
            query=context.query
        ) + critique_context
        
        critique = ""
        # Optimized: Limit critique to 600 tokens for faster validation
        async for chunk in self.llm.generate_stream(
            prompt=critique_prompt,
            temperature=0,  # Deterministic for faster, more consistent analysis
            max_tokens=600  # Aggressively reduced from 1000 for speed (still sufficient for quality check)
        ):
            critique += chunk
        
        # Parse critique scores
        scores = self._parse_critique_scores(critique)
        overall_score = scores.get("overall", 7)
        needs_improvement = scores.get("needs_improvement", True)
        
        yield self.create_event(
            AgentEventType.OBSERVATION,
            f"📊 Critique Results:\n"
            f"- Accuracy: {scores.get('accuracy', '?')}/10\n"
            f"- Completeness: {scores.get('completeness', '?')}/10\n"
            f"- Coherence: {scores.get('coherence', '?')}/10\n"
            f"- Quality: {scores.get('quality', '?')}/10\n"
            f"- Relevance: {scores.get('relevance', '?')}/10\n"
            f"- Overall: {overall_score}/10\n"
            f"- Needs Improvement: {'Yes' if needs_improvement else 'No'}",
            {
                "scores": scores,
                "event_type": "reflect_validation"
            }
        )
        
        # Extract priority fixes
        priority_fixes = self._extract_priority_fixes(critique)
        if priority_fixes:
            yield self.create_event(
                AgentEventType.THOUGHT,
                "🔧 Priority Fixes:\n" + "\n".join([f"- {fix}" for fix in priority_fixes])
            )
        
        final_output = react_output
        
        # ===============================
        # PHASE 2: IMPROVE (if needed)
        # ===============================
        if needs_improvement or overall_score < 8:
            yield self.create_event(
                AgentEventType.STATUS,
                "✨ Phase 2: Improve - Rewriting based on critique..."
            )
            
            improve_prompt = self.IMPROVE_PROMPT.format(
                content=react_output[:2500],
                critique=critique[:1500]
            )
            
            improved = ""
            # Optimized: Limit improvement to 1200 tokens for faster processing
            async for chunk in self.llm.generate_stream(
                prompt=improve_prompt,
                temperature=0,  # Deterministic for faster, more consistent improvement
                max_tokens=1200  # Reduced from 2000 for speed while maintaining quality
            ):
                improved += chunk
            
            if improved and len(improved) > len(react_output) * 0.5:
                final_output = improved
                yield self.create_event(
                    AgentEventType.ACTION,
                    f"✅ Content improved ({len(react_output)} → {len(improved)} chars)"
                )
            else:
                yield self.create_event(
                    AgentEventType.THOUGHT,
                    "Original content retained (improvement not substantial)"
                )
        else:
            yield self.create_event(
                AgentEventType.THOUGHT,
                f"✅ Content quality is good (score: {overall_score}/10). Minimal changes needed."
            )
        
        # ===============================
        # PHASE 3: FINAL OUTPUT
        # ===============================
        yield self.create_event(
            AgentEventType.STATUS,
            "📤 Phase 3: Final - Preparing output..."
        )
        
        # Store in context
        context.metadata["reflect_output"] = final_output
        context.metadata["reflect_scores"] = scores
        context.metadata["reflect_critique"] = critique[:1000]
        
        # Build storyboard only for storyboard-specific domains or when explicitly needed
        # For normal chatbot mode, skip storyboard creation
        storyboard_domains = ["product_demo", "education", "marketing", "film_style", "gaming", "medical"]
        should_create_storyboard = (
            context.domain in storyboard_domains or 
            context.metadata.get("create_storyboard", False) or
            len(react_scenes) > 0
        )
        
        scenes = []
        if should_create_storyboard:
            scenes = self._build_scenes(final_output, react_scenes, context)
            if scenes:
                storyboard = self._build_storyboard(context, scenes, scores)
                context.storyboard = storyboard
            else:
                context.storyboard = None
        else:
            context.storyboard = None
        
        # Save to memory
        await self.tme.add_memory(
            session_id=context.session_id,
            content=f"ReFlect score: {overall_score}/10. Improvements: {', '.join(priority_fixes[:3])}",
            memory_type="reflect_result",
            tags=["reflect", "quality", str(overall_score)]
        )
        
        yield self.create_event(
            AgentEventType.MEMORY_UPDATE,
            "Saved reflection results to memory"
        )
        
        # Build completion message with template validation info
        template_status = ""
        template_metadata = {}
        if template_validation:
            template_status = (
                f"\n🔍 Template Validation:\n"
                f"  • Instructional Designer: {'✅' if template_validation['instructional_designer_present'] else '❌'}\n"
                f"  • Unique Keys: {'✅' if template_validation['has_unique_keys'] else '❌'}\n"
                f"  • Schema Valid: {'✅' if template_validation['schema_valid'] else '❌'}\n"
                f"  • Template Valid: {'✅' if template_validation['is_valid'] else '❌'}"
            )
            template_metadata = {
                "template_valid": template_validation["is_valid"],
                "instructional_designer_present": template_validation["instructional_designer_present"],
                "unique_keys": template_validation["has_unique_keys"],
                "template_validation_score": template_validation["overall_score"]
            }
        
        # Determine storyboard info for completion message
        storyboard_info = ""
        storyboard_id = None
        if context.storyboard:
            storyboard_info = f"\n🎬 Storyboard: Created ({len(scenes)} scenes)"
            storyboard_id = context.storyboard.id
        
        yield self.create_event(
            AgentEventType.COMPLETE,
            f"✅ ReFlect complete!\n\n"
            f"🎯 Domain: {detected_domain}\n"
            f"📊 Final Quality Score: {overall_score}/10\n"
            f"📝 Output: {len(final_output)} characters"
            f"{storyboard_info}"
            f"{template_status}",
            {
                "quality_score": overall_score,
                "output_length": len(final_output),
                "sections": len(scenes),
                "storyboard_id": storyboard_id,
                "detected_domain": detected_domain,
                "final_output": final_output,
                "event_type": "final_output",
                **template_metadata
            }
        )
    
    def _parse_critique_scores(self, critique: str) -> Dict[str, Any]:
        """Parse scores from the critique."""
        scores = {
            "accuracy": 7,
            "completeness": 7,
            "coherence": 7,
            "quality": 7,
            "relevance": 7,
            "overall": 7,
            "needs_improvement": True
        }
        
        # Extract individual scores
        patterns = {
            "accuracy": r"ACCURACY[:\s]+.*?(\d+)\s*/?\s*10",
            "completeness": r"COMPLETENESS[:\s]+.*?(\d+)\s*/?\s*10",
            "coherence": r"COHERENCE[:\s]+.*?(\d+)\s*/?\s*10",
            "quality": r"QUALITY[:\s]+.*?(\d+)\s*/?\s*10",
            "relevance": r"RELEVANCE[:\s]+.*?(\d+)\s*/?\s*10",
            "overall": r"Overall\s*Score[:\s]+(\d+)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, critique, re.IGNORECASE)
            if match:
                scores[key] = int(match.group(1))
        
        # Calculate overall if not found
        if scores["overall"] == 7:
            total = sum([scores[k] for k in ["accuracy", "completeness", "coherence", "quality", "relevance"]])
            scores["overall"] = round(total / 5)
        
        # Determine if improvement needed
        needs_match = re.search(r"Needs\s*Improvement[:\s]+(yes|no)", critique, re.IGNORECASE)
        if needs_match:
            scores["needs_improvement"] = needs_match.group(1).lower() == "yes"
        else:
            scores["needs_improvement"] = scores["overall"] < 8
        
        return scores
    
    def _extract_priority_fixes(self, critique: str) -> List[str]:
        """Extract priority fixes from critique."""
        fixes = []
        
        # Look for priority fixes section
        priority_match = re.search(r"Priority\s*Fixes[:\s]+([\s\S]+?)(?:\n\n|$)", critique, re.IGNORECASE)
        if priority_match:
            fixes_text = priority_match.group(1)
            # Extract bullet points
            fix_items = re.findall(r"[-•*\d.]\s*(.+?)(?=[-•*\d.]|\n\n|$)", fixes_text)
            fixes = [f.strip() for f in fix_items if f.strip()][:5]
        
        # If no structured fixes found, look for "Issues" mentions
        if not fixes:
            issues = re.findall(r"Issues?:\s*(.+?)(?=\n|$)", critique, re.IGNORECASE)
            fixes = [i.strip() for i in issues if i.strip() and i.strip() != "None"][:5]
        
        return fixes
    
    def _build_scenes(
        self, 
        content: str, 
        react_scenes: List, 
        context: AgentContext
    ) -> List[Scene]:
        """Build scenes from content."""
        scenes = []
        
        # Use ReACT scenes if available
        for scene_data in react_scenes:
            if isinstance(scene_data, dict):
                scenes.append(Scene(**scene_data))
        
        # If no scenes, try to extract from content
        if not scenes:
            patterns = [
                r"(?:##|###)\s*(\d+)[.:\s]+(.+?)(?=(?:##|###)\s*\d+|$)",
                r"(?:Scene|Section|Part)\s*(\d+)[:\s]+(.+?)(?=(?:Scene|Section|Part)\s*\d+|$)"
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    for num, text in matches[:10]:
                        title = text.split('\n')[0].strip()[:100]
                        desc = text[:500] if len(text) > 100 else text
                        scenes.append(Scene(
                            scene_number=int(num),
                            title=title,
                            description=desc.strip(),
                            visual_elements=[],
                            camera_direction=""
                        ))
                    break
        
        return scenes
    
    def _build_storyboard(
        self,
        context: AgentContext,
        scenes: List[Scene],
        scores: Dict
    ) -> Storyboard:
        """Build the final storyboard."""
        status = "complete" if scores.get("overall", 0) >= 7 else "needs_review"
        
        return Storyboard(
            session_id=context.session_id,
            domain=context.domain,
            query=context.query,
            title=context.master_plan.title if context.master_plan else f"{context.domain} Output",
            master_plan=context.master_plan,
            scenes=scenes,
            status=status
        )
