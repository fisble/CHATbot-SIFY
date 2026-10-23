"""
ReACT Agent - Reason + Act Loop ("Interactive Multi-Step Reasoning")

Pattern: Thought → Action → Observation → Thought → ... → Final Answer

This is the EXECUTOR component of ThinkerLLM - executing PreAct's plan step by step.

This agent alternates between:
1. THOUGHT: Reasoning about what to do next
2. ACTION: Taking an action (tool call, search, generate, build_template)
3. OBSERVATION: Observing the result
4. Repeat until task complete

Enhanced for Dynamic Template Generation:
- BUILD_TEMPLATE: Generate domain-specific template with unique keys
- GENERATE_SKILLS: Generate domain-specific skill list
- GENERATE_CAPABILITIES: Generate unique capability keys

Use when:
- Task has unknown steps
- Need to interact with tools
- Need to gather information dynamically
- Need to generate domain-specific templates

Strengths: Dynamic, flexible, best for agentic behavior
Weaknesses: More tokens, slower, can hallucinate without constraints
"""

from typing import AsyncGenerator, Optional, Dict, Any, List
import json
import re
import uuid
from datetime import datetime

from .base import BaseAgent, AgentContext
from models.schemas import AgentEvent, AgentName, AgentEventType, Scene
from config import settings


class ReActAgent(BaseAgent):
    """
    ReACT Agent - Interactive Multi-Step Reasoning
    
    Implements the Thought → Action → Observation loop:
    - THOUGHT: What should I do next?
    - ACTION: Execute an action (search, generate, tool call)
    - OBSERVATION: What was the result?
    - Repeat until FINAL ANSWER
    """
    
    SYSTEM_PROMPT = """You are ReACT, the EXECUTOR and CONTENT CREATOR component of ThinkerLLM.

Your role is to EXECUTE PreAct's plan by CREATING ACTUAL CONTENT - not more plans!

## CRITICAL: OUTPUT TYPE AWARENESS
- If user asked a QUESTION → Provide a comprehensive ANSWER (not a video/storyboard)
- If user asked for ANALYSIS → Create an analysis DOCUMENT
- If user asked for a COURSE → Create actual LESSON content
- If user asked for a GUIDE → Create a step-by-step GUIDE
- ONLY create video/storyboard content if user EXPLICITLY requested it

DO NOT default to creating "videos" or "2 minute videos". This is NOT a video production system unless explicitly asked.

## YOUR MISSION
PreAct created a plan. YOU must now CREATE THE ACTUAL CONTENT by executing each step.
- If the user asked for a COURSE → Write actual lessons, modules, and exercises
- If the user asked for ANALYSIS → Write the actual analysis with data and insights
- If the user asked for a GUIDE → Write actual step-by-step instructions
- If the user asked a QUESTION → Provide a thorough, well-structured answer
- DO NOT create another plan. CREATE THE REAL CONTENT.

## EXECUTION PATTERN
THOUGHT: [Which step you're working on and what content you'll create]
ACTION: GENERATE - [Describe the actual content to create for this step]
OBSERVATION: [You receive the generated content]

## AVAILABLE ACTIONS
- GENERATE: Create ACTUAL content (answers, lessons, analysis, guides, etc.)
- SEARCH: Research information needed
- FINAL_ANSWER: Compile all generated content into final deliverable

## CRITICAL RULES
1. CREATE CONTENT, NOT PLANS - You are the executor, not the planner
2. Match the OUTPUT TYPE to what the user actually requested
3. For courses: Write actual lesson content with explanations, examples, and exercises
4. For analysis: Write actual findings, data interpretation, and recommendations
5. For questions: Provide comprehensive, well-structured answers
6. Be DETAILED and COMPREHENSIVE in your GENERATE actions
7. FINAL_ANSWER compiles everything into the user's requested format

## EXAMPLE - Course Creation
User wants: "Create a Python basics course"
PreAct planned: 1) Introduction, 2) Variables, 3) Functions

THOUGHT: Step 1 - Creating actual Introduction lesson content
ACTION: GENERATE - Write Introduction lesson: What is Python, why learn it, setting up environment, first "Hello World" program with code example
OBSERVATION: [Actual lesson content with code examples]

THOUGHT: Step 2 - Creating actual Variables lesson content  
ACTION: GENERATE - Write Variables lesson: What are variables, data types (int, str, float, bool), variable naming, type conversion, with 5 code examples
OBSERVATION: [Actual lesson content with code examples]

THOUGHT: Step 3 - Creating actual Functions lesson
ACTION: GENERATE - Write Functions lesson: Defining functions, parameters, return values, scope, 3 practice exercises
OBSERVATION: [Actual lesson content with exercises]

THOUGHT: All lessons created. Compiling course.
ACTION: FINAL_ANSWER -

# Python Basics Course

## Module 1: Introduction to Python
[Full introduction lesson content...]

## Module 2: Variables and Data Types  
[Full variables lesson content...]

## Module 3: Functions
[Full functions lesson content with exercises...]"""

    @property
    def name(self) -> AgentName:
        return AgentName.REACT
    
    async def run(self, context: AgentContext) -> AsyncGenerator[AgentEvent, None]:
        """
        Execute the ReACT reasoning loop.
        Thought → Action → Observation → ... → Final Answer
        """
        yield self.create_event(
            AgentEventType.STATUS,
            "⚡ ReACT: Starting interactive reasoning loop..."
        )
        
        # Get the reasoning plan from PreAct
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        steps = reasoning_plan.get("steps", [])
        
        yield self.create_event(
            AgentEventType.THOUGHT,
            f"Task: {context.query}\nFollowing plan with {len(steps)} steps..."
        )
        
        # Initialize tracking variables before first use
        completed_steps = set()  # Track completed plan steps
        step_summaries = {}  # Store summaries of completed steps for context compression
        
        # Build initial context (will be optimized per iteration)
        task_context = self._build_task_context(context, reasoning_plan, completed_steps, step_summaries)
        
        # Calculate max iterations based on plan steps
        # Optimized: Use 1.5 iterations per step (more efficient) + 2 for final answer
        # This allows faster completion while still ensuring quality
        num_steps = len(steps) if steps else 3
        calculated_max = int(num_steps * 1.5) + 2  # Optimized: 1.5 iterations per step + 2 for final
        dynamic_max_iterations = max(calculated_max, min(settings.react_max_iterations, 12))  # Cap at 12 for speed
        
        yield self.create_event(
            AgentEventType.STATUS,
            f"📋 Plan has {num_steps} steps, allowing up to {dynamic_max_iterations} iterations"
        )
        
        # Run the reasoning loop
        iteration = 0
        conversation_history = []
        final_output = ""
        generated_content = []  # Store content from GENERATE actions
        scenes = []
        
        while iteration < dynamic_max_iterations:
            iteration += 1
            
            yield self.create_event(
                AgentEventType.STATUS,
                f"🔄 ReACT iteration {iteration}/{dynamic_max_iterations} (Steps completed: {len(completed_steps)}/{num_steps})"
            )
            
            # Rebuild task context with current progress (compressed completed steps)
            task_context = self._build_task_context(context, reasoning_plan, completed_steps, step_summaries)
            
            # Build prompt with conversation history and progress tracking
            prompt = self._build_iteration_prompt(
                task_context, 
                conversation_history,
                iteration,
                completed_steps,
                num_steps
            )
            
            # Generate next step
            response = ""
            async for chunk in self.llm.generate_stream(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=500  # Limit THOUGHT generation for speed
            ):
                response += chunk
            
            # Parse the response
            thought, action, action_input = self._parse_response(response)
            
            # Emit THOUGHT
            if thought:
                yield self.create_event(
                    AgentEventType.THOUGHT,
                    f"💭 THOUGHT: {thought}"
                )
                # Optimized: Truncate thought in history to prevent token bloat
                # Keep only first 300 chars of thought for history
                thought_summary = thought[:300] + "..." if len(thought) > 300 else thought
                conversation_history.append(f"THOUGHT: {thought_summary}")
            
            # Check for FINAL_ANSWER
            if action and action.upper() == "FINAL_ANSWER":
                final_output = action_input or response
                
                yield self.create_event(
                    AgentEventType.ACTION,
                    f"✅ FINAL_ANSWER reached"
                )
                
                # Emit the final output content as a scene event so UI can display it
                # Include web sources if available
                event_metadata = {
                    "final_output": final_output,
                    "event_type": "react_output"
                }
                # Add web sources to metadata if available
                if "web_sources" in context.metadata and context.metadata["web_sources"]:
                    event_metadata["web_sources"] = context.metadata["web_sources"]
                
                yield self.create_event(
                    AgentEventType.SCENE,
                    f"📄 ReAct Output:\n\n{final_output}",
                    event_metadata
                )
                
                # Extract any structured content
                scenes = self._extract_scenes(final_output, context)
                break
            
            # Emit ACTION
            if action:
                yield self.create_event(
                    AgentEventType.ACTION,
                    f"⚡ ACTION: {action} - {action_input[:100]}..."
                )
                # Optimized: Truncate action input in history to prevent token bloat
                # Keep only first 200 chars of action input for history
                action_summary = action_input[:200] + "..." if len(action_input) > 200 else action_input
                conversation_history.append(f"ACTION: {action} - {action_summary}")
                
                # Execute the action and get observation
                observation = await self._execute_action(action, action_input, context)
                
                # Track step completion for GENERATE actions (main content generation)
                if action.upper() == "GENERATE":
                    # Calculate next step number (1-indexed)
                    next_step_num = len(completed_steps) + 1
                    completed_steps.add(next_step_num)
                    
                    # Create summary of completed step for context compression
                    step_title = ""
                    if steps and next_step_num <= len(steps):
                        step_obj = steps[next_step_num - 1] if isinstance(steps[0], dict) else None
                        if step_obj and isinstance(step_obj, dict):
                            step_title = step_obj.get('title', f'Step {next_step_num}')
                    
                    # Summarize the generated content for future context
                    summary = f"{step_title} - Content generated" if step_title else f"Step {next_step_num} - Content generated"
                    step_summaries[next_step_num] = summary
                    
                    yield self.create_event(
                        AgentEventType.STATUS,
                        f"✅ Step {len(completed_steps)}/{num_steps} completed"
                    )
                
                # Emit OBSERVATION
                yield self.create_event(
                    AgentEventType.OBSERVATION,
                    f"👁️ OBSERVATION: {observation[:300]}..."
                )
                # Optimized: Truncate observation in history to prevent token bloat
                # Keep only first 500 chars instead of full 18K+ chars
                observation_summary = observation[:500] + "..." if len(observation) > 500 else observation
                conversation_history.append(f"OBSERVATION: {observation_summary}")
            else:
                # No clear action, treat response as progress
                conversation_history.append(f"RESPONSE: {response[:500]}")
                final_output += response
        
        # If no FINAL_ANSWER was reached, use fallback strategies
        if not final_output:
            yield self.create_event(
                AgentEventType.STATUS,
                "⚠️ No explicit FINAL_ANSWER - using fallback compilation..."
            )
            
            # Strategy 1: Use generated content if available
            if "generated_content" in context.metadata and context.metadata["generated_content"]:
                generated = context.metadata["generated_content"]
                final_output = "\n\n".join(generated)
                
                # Include web sources if available
                event_metadata = {
                    "final_output": final_output,
                    "event_type": "react_output"
                }
                if "web_sources" in context.metadata and context.metadata["web_sources"]:
                    event_metadata["web_sources"] = context.metadata["web_sources"]
                
                yield self.create_event(
                    AgentEventType.SCENE,
                    f"ReAct Output (compiled from {len(generated)} generations):\n\n{final_output[:2000]}...",
                    event_metadata
                )
                scenes = self._extract_scenes(final_output, context)
            
            # Strategy 2: Generate a direct answer if no content was generated
            elif not final_output:
                yield self.create_event(
                    AgentEventType.STATUS,
                    "Generating direct response..."
                )
                final_output = await self._generate_fallback_response(context)
                
                # Include web sources if available
                event_metadata = {
                    "final_output": final_output,
                    "event_type": "react_output"
                }
                if "web_sources" in context.metadata and context.metadata["web_sources"]:
                    event_metadata["web_sources"] = context.metadata["web_sources"]
                
                yield self.create_event(
                    AgentEventType.SCENE,
                    f"ReAct Output (fallback):\n\n{final_output[:2000]}...",
                    event_metadata
                )
                scenes = self._extract_scenes(final_output, context)
        
        # Store output in context
        context.metadata["react_output"] = final_output
        context.metadata["react_scenes"] = [s.model_dump() for s in scenes]
        context.metadata["react_iterations"] = iteration
        
        # Store web sources if web search was used during generation
        if "web_sources" in context.metadata and context.metadata["web_sources"]:
            # Deduplicate sources by URL
            seen_urls = set()
            unique_sources = []
            for source in context.metadata["web_sources"]:
                url = source.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_sources.append(source)
            context.metadata["react_web_sources"] = unique_sources
            print(f"[REACT] Stored {len(unique_sources)} web sources in metadata")
        
        
        # Save to memory
        await self.tme.add_memory(
            session_id=context.session_id,
            content=f"ReACT completed in {iteration} iterations",
            memory_type="react_result",
            tags=["react", "reasoning", context.domain]
        )
        
        yield self.create_event(
            AgentEventType.MEMORY_UPDATE,
            "Saved reasoning results to memory"
        )
        
        # Include template-specific info if generated
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        detected_domain = reasoning_plan.get("detected_domain", context.domain)
        template_valid = context.metadata.get("template_valid", False)
        generated_skills = context.metadata.get("generated_skills", [])
        generated_capabilities = context.metadata.get("generated_capabilities", {})
        
        yield self.create_event(
            AgentEventType.COMPLETE,
            f"✅ ReACT complete after {iteration} iterations (max allowed: {dynamic_max_iterations})\n"
            f"🎯 Domain: {detected_domain}\n"
            f"📄 Output: {len(final_output)} chars\n"
            f"👥 Skills: {len(generated_skills)} generated\n"
            f"🔧 Capabilities: {len(generated_capabilities)} keys\n"
            f"✨ Template Valid: {'Yes' if template_valid else 'Pending validation'}",
            {
                "iterations": iteration,
                "max_iterations": dynamic_max_iterations,
                "output_length": len(final_output),
                "scenes_generated": len(scenes),
                "detected_domain": detected_domain,
                "template_valid": template_valid,
                "skills_count": len(generated_skills),
                "capabilities_count": len(generated_capabilities)
            }
        )
    
    def _build_task_context(self, context: AgentContext, reasoning_plan: Dict, completed_steps: set = None, step_summaries: Dict = None) -> str:
        """Build the task context from PreAct's plan - optimized with step compression."""
        completed_steps = completed_steps or set()
        step_summaries = step_summaries or {}
        
        steps_text = ""
        steps = reasoning_plan.get("steps", [])
        
        for idx, step in enumerate(steps):
            if isinstance(step, dict):
                step_num = step.get('step_number', idx + 1)
                step_id = step_num if isinstance(step_num, int) else (idx + 1)
                
                # If step is completed, use summary (compressed)
                if step_id in completed_steps and step_id in step_summaries:
                    steps_text += f"- Step {step_id}: ✓ {step_summaries[step_id]}\n"
                else:
                    # For active/upcoming steps, show full details
                    steps_text += f"- Step {step_id}: {step.get('title', 'Untitled')}\n"
                    # Only include expected_output for active steps (not completed ones)
                    if step_id not in completed_steps:
                        expected_output = step.get('expected_output', 'N/A')
                        if expected_output and expected_output != 'N/A':
                            steps_text += f"  Expected output: {expected_output}\n"
            else:
                steps_text += f"- {step}\n"
        
        detected_domain = reasoning_plan.get('detected_domain', context.domain)
        
        # Check if this is a template generation task
        is_template_task = self._is_template_task(context.query)
        
        # Base context for all tasks
        base_context = f"""## TASK
Domain: {detected_domain}
Request: {context.query}

## PREACT PLAN
Understanding: {reasoning_plan.get('task_understanding', context.query)}
Approach: {reasoning_plan.get('approach', 'Step-by-step reasoning')}

## STEPS TO FOLLOW
{steps_text or '- Complete the requested task step by step'}

## CONSTRAINTS
{chr(10).join(['- ' + c for c in reasoning_plan.get('constraints', ['Stay accurate', 'Be thorough'])])}

## SUCCESS CRITERIA
{chr(10).join(['- ' + c for c in reasoning_plan.get('success_criteria', ['Task fully completed'])])}
"""
        
        # Add template-specific context only for template tasks
        if is_template_task:
            domain_skills = reasoning_plan.get('domain_skills', ['Instructional Designer'])
            domain_capabilities = reasoning_plan.get('domain_capabilities', [])
            template_id = reasoning_plan.get('template_id', str(uuid.uuid4()))
            
            template_context = f"""
## TEMPLATE GENERATION REQUIREMENTS
### Skills (must include in template):
{chr(10).join(['- ' + s for s in domain_skills])}

### Capability Keys (must generate unique keys):
{chr(10).join(['- ' + c for c in domain_capabilities])}

## TEMPLATE SCHEMA
Your final output must follow this structure:
{{
  "{detected_domain}": {{
    "id": "{template_id}",
    "domain": "{detected_domain}",
    "skills": ["Instructional Designer", ...other domain skills...],
    "capabilities": {{...unique domain-specific keys...}}
  }}
}}
"""
            return base_context + template_context
        else:
            # Detect content type for specific guidance
            query_lower = context.query.lower()
            is_course = any(w in query_lower for w in ['course', 'curriculum', 'lesson', 'module', 'training'])
            is_analysis = any(w in query_lower for w in ['analysis', 'analyze', 'research', 'study'])
            
            if is_course:
                output_guidance = """
## YOUR TASK: CREATE ACTUAL COURSE CONTENT
You are NOT planning - you are CREATING the actual course content.

For each step, use GENERATE to write:
- Full lesson content (not outlines)
- Code examples with explanations (if technical)
- Practice exercises with solutions
- Key takeaways for each section

IMPORTANT: Write content a student would actually READ and LEARN from.
Do NOT write another outline or plan. Write ACTUAL educational content.

FINAL_ANSWER must contain the complete course with all lessons written out.
"""
            elif is_analysis:
                output_guidance = """
## YOUR TASK: CREATE ACTUAL ANALYSIS
You are NOT planning - you are WRITING the actual analysis.

For each step, use GENERATE to write:
- Actual findings and data interpretations
- Specific insights with supporting evidence
- Concrete recommendations
- Visualizable data points

FINAL_ANSWER must contain the complete analysis document.
"""
            else:
                output_guidance = """
## YOUR TASK: CREATE ACTUAL CONTENT
You are the EXECUTOR - create the actual deliverable the user requested.

For each step, use GENERATE to create real, usable content:
- Detailed explanations and information
- Examples and illustrations
- Actionable recommendations
- Professional formatting

Do NOT create another plan. CREATE the actual content.
"""
            return base_context + output_guidance
    
    def _is_template_task(self, query: str) -> bool:
        """Check if the query is asking for template generation."""
        template_keywords = [
            "template", "json template", "domain template", "generate template",
            "create template", "build template", "schema", "json schema"
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in template_keywords)
    
    def _build_iteration_prompt(
        self, 
        task_context: str, 
        history: List[str],
        iteration: int,
        completed_steps: set = None,
        total_steps: int = 0
    ) -> str:
        """Build the prompt for current iteration - optimized with history compression."""
        # Optimized: Use only last 4 history items (reduced from 6) to save tokens
        # Keep recent context but limit accumulation
        # For older items, summarize instead of full text
        if history:
            # Keep last 4 items in full detail
            recent_items = history[-4:] if len(history) > 4 else history
            # Summarize older items if they exist
            if len(history) > 4:
                older_count = len(history) - 4
                summary = f"[{older_count} previous iterations completed]"
                history_items = [summary] + recent_items
            else:
                history_items = recent_items
            history_text = "\n".join(history_items)
        else:
            history_text = "No previous steps yet."
        
        # Build progress indicator
        completed_steps = completed_steps or set()
        next_step_num = len(completed_steps) + 1
        remaining_steps = total_steps - len(completed_steps)
        
        if remaining_steps > 0:
            progress_text = f"""## PROGRESS
Steps completed: {len(completed_steps)}/{total_steps}
NEXT: Execute Step {next_step_num}

REMINDER: You are CREATING CONTENT, not planning.
Use ACTION: GENERATE to write the ACTUAL content for Step {next_step_num}.
Be detailed and comprehensive in your generation."""
        else:
            progress_text = f"""## PROGRESS  
All {total_steps} steps completed!

NOW: Use ACTION: FINAL_ANSWER to compile ALL your generated content into the final deliverable.
Include ALL the content you created - full lessons, analyses, guides, etc.
Format it professionally with headings and sections."""
        
        return f"""{task_context}

## EXECUTION HISTORY
{history_text}

{progress_text}

## YOUR TURN (THOUGHT then ACTION):"""
    
    def _parse_response(self, response: str) -> tuple:
        """Parse THOUGHT, ACTION, and action input from response."""
        thought = ""
        action = ""
        action_input = ""
        
        # Extract THOUGHT
        thought_match = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|$)", response, re.IGNORECASE | re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        
        # Extract ACTION
        action_match = re.search(r"ACTION:\s*(\w+)\s*[-:]\s*(.+?)(?=THOUGHT:|OBSERVATION:|$)", response, re.IGNORECASE | re.DOTALL)
        if action_match:
            action = action_match.group(1).strip()
            action_input = action_match.group(2).strip()
        else:
            # Try simpler pattern
            action_match = re.search(r"ACTION:\s*(\w+)", response, re.IGNORECASE)
            if action_match:
                action = action_match.group(1).strip()
                # Get everything after action name
                after_action = response[action_match.end():]
                action_input = after_action.split("THOUGHT")[0].split("OBSERVATION")[0].strip(" -:\n")
        
        return thought, action, action_input
    
    async def _execute_action(self, action: str, action_input: str, context: AgentContext) -> str:
        """Execute the specified action and return observation."""
        action_upper = action.upper()
        
        if action_upper == "SEARCH":
            return await self._action_search(action_input, context)
        elif action_upper == "GENERATE":
            return await self._action_generate(action_input, context)
        elif action_upper == "ANALYZE":
            return await self._action_analyze(action_input, context)
        elif action_upper == "REMEMBER":
            return await self._action_remember(action_input, context)
        elif action_upper == "BUILD_TEMPLATE":
            return await self._action_build_template(action_input, context)
        elif action_upper == "GENERATE_SKILLS":
            return await self._action_generate_skills(action_input, context)
        elif action_upper == "GENERATE_CAPABILITIES":
            return await self._action_generate_capabilities(action_input, context)
        else:
            return f"Unknown action '{action}'. Available: SEARCH, GENERATE, ANALYZE, REMEMBER, BUILD_TEMPLATE, GENERATE_SKILLS, GENERATE_CAPABILITIES, FINAL_ANSWER"
    
    async def _action_search(self, query: str, context: AgentContext) -> str:
        """Execute SEARCH action using RAG and optionally web search."""
        # Check if web search is enabled (only when user explicitly enables it)
        enable_web_search = context.metadata.get("enable_web_search", False)
        
        results_text = []
        
        # Always try RAG search first (internal knowledge base)
        try:
            rag_results = await self.rag.search(
                query=query,
                domain=context.domain,
                n_results=3
            )
            if rag_results:
                results_text.append("RAG Search Results (Knowledge Base):")
                results_text.append("\n".join([
                    f"- {r.content[:200]}..." for r in rag_results
                ]))
        except Exception as e:
            results_text.append(f"RAG search error: {str(e)[:100]}")
        
        # Web search only if explicitly enabled by user
        if enable_web_search:
            try:
                from services.web_search_service import web_search
                web_results = web_search(query, top_k=5)
                if web_results and len(web_results) > 0:
                    results_text.append("\n\nWeb Search Results:")
                    results_text.append("\n".join([
                        f"[{i+1}] {r.get('title', 'No title')}: {r.get('snippet', 'No snippet')[:150]}... (Source: {r.get('url', 'N/A')})"
                        for i, r in enumerate(web_results)
                    ]))
                else:
                    results_text.append("\n\nWeb search: No additional results found.")
            except Exception as e:
                results_text.append(f"\n\nWeb search error: {str(e)[:100]}")
        
        if results_text:
            return "\n".join(results_text)
        return "No relevant results found."
    
    async def _action_generate(self, instruction: str, context: AgentContext) -> str:
        """Execute GENERATE action to create ACTUAL content (not plans)."""
        
        # Check if web search is enabled - if so, search first for context
        enable_web_search = context.metadata.get("enable_web_search", False)
        web_context = ""
        web_sources = []
        
        if enable_web_search:
            try:
                from services.web_search_service import web_search
                # Extract search query from instruction or use original query
                search_query = context.query or instruction[:100]
                web_results = web_search(search_query, top_k=5)
                if web_results and len(web_results) > 0:
                    web_sources = web_results  # Store for later use
                    web_context = "\n\n## Additional Context (Optional Web Search Results):\n"
                    web_context += "These are supplementary sources that may provide current information. Use them to enhance your content when relevant, but follow your normal reasoning process:\n\n"
                    web_context += "\n".join([
                        f"[{i+1}] {r.get('title', 'No title')}: {r.get('snippet', 'No snippet')} (Source: {r.get('url', 'N/A')})"
                        for i, r in enumerate(web_results)
                    ])
                    web_context += "\n\nNote: These are supplementary sources. Use your knowledge and reasoning first, and cite these sources [1], [2], etc. only when you actually use information from them."
            except Exception as e:
                print(f"[GENERATE] Web search error: {str(e)[:100]}")
                web_context = "\n\n[Note: Web search unavailable, proceeding with knowledge base only]"
        
        # Get task type from context
        query_lower = context.query.lower()
        is_course = any(w in query_lower for w in ['course', 'curriculum', 'lesson', 'module', 'training', 'tutorial'])
        is_analysis = any(w in query_lower for w in ['analysis', 'analyze', 'compare', 'evaluate', 'assess'])
        is_guide = any(w in query_lower for w in ['guide', 'how to', 'steps', 'process', 'procedure'])
        
        # Build content-specific prompt
        if is_course:
            prompt = f"""CREATE ACTUAL COURSE CONTENT for: {instruction}
{web_context}
Original Request: {context.query}

You are now WRITING THE ACTUAL CONTENT, not planning. Generate:
- Detailed lesson content with explanations
- Code examples (if technical)
- Practice exercises
- Key learning points

IMPORTANT: Write the ACTUAL educational content that a student would read and learn from.
Do NOT write another plan or outline. Write the REAL content.
{web_context and "Note: The web search context above is supplementary. Use your knowledge and reasoning first, and reference web sources only when they add value." or ""}

Generate the complete content now:"""
        elif is_analysis:
            prompt = f"""WRITE ACTUAL ANALYSIS for: {instruction}
{web_context}
Original Request: {context.query}

Produce a comprehensive analysis including:
- Data and findings
- Insights and interpretations
- Recommendations
- Supporting evidence
{web_context and "Note: The web search context above is supplementary. Use your knowledge and reasoning first, and reference web sources only when they add value." or ""}

Write the complete analysis:"""
        elif is_guide:
            prompt = f"""WRITE ACTUAL GUIDE CONTENT for: {instruction}
{web_context}
Original Request: {context.query}

Create detailed guide content with:
- Step-by-step instructions
- Examples and explanations
- Tips and best practices
- Common pitfalls to avoid
{web_context and "Note: The web search context above is supplementary. Use your knowledge and reasoning first, and reference web sources only when they add value." or ""}

Write the complete guide:"""
        else:
            prompt = f"""CREATE ACTUAL CONTENT for: {instruction}
{web_context}
Original Request: {context.query}
Domain: {context.domain}

IMPORTANT: You are CREATING the final content, not planning.
Write comprehensive, detailed content that directly addresses the request.
Include examples, explanations, and actionable information.
{web_context and "Note: The web search context above is supplementary. Use your knowledge and reasoning first, and reference web sources only when they add value." or ""}

Generate the complete content:"""
        
        result = ""
        # Optimized for speed: Reduced max_tokens to 800 for faster generation
        # GPT-3.5-turbo generates ~15-20ms per token vs GPT-4's 30-50ms
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            temperature=0.7,
            max_tokens=800  # Further reduced: 1200 -> 800 for 3-4min total time
        ):
            result += chunk
        
        # Store full generated content for later use
        if "generated_content" not in context.metadata:
            context.metadata["generated_content"] = []
        context.metadata["generated_content"].append(result)
        
        # Store web sources if web search was used
        if enable_web_search and web_sources:
            if "web_sources" not in context.metadata:
                context.metadata["web_sources"] = []
            context.metadata["web_sources"].extend(web_sources)
        
        # Return more of the result for context
        sources_note = f" (with {len(web_sources)} web sources)" if web_sources else ""
        return f"✅ Generated content ({len(result)} chars){sources_note}:\n{result[:800]}..."
    
    async def _action_analyze(self, subject: str, context: AgentContext) -> str:
        """Execute ANALYZE action."""
        prompt = f"""Analyze: {subject}

Provide a brief analysis considering:
- Key points
- Patterns or trends
- Important insights

Analysis:"""
        
        result = ""
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            temperature=0.5
        ):
            result += chunk
        
        return f"Analysis:\n{result[:400]}..."
    
    async def _action_remember(self, content: str, context: AgentContext) -> str:
        """Execute REMEMBER action to store in memory."""
        try:
            await self.tme.add_memory(
                session_id=context.session_id,
                content=content,
                memory_type="react_memory",
                tags=["react", "remembered"]
            )
            return f"Stored in memory: {content[:100]}..."
        except Exception as e:
            return f"Memory error: {str(e)[:100]}"
    
    async def _action_build_template(self, instruction: str, context: AgentContext) -> str:
        """Execute BUILD_TEMPLATE action to create a complete domain template."""
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        detected_domain = reasoning_plan.get("detected_domain", context.domain)
        domain_skills = reasoning_plan.get("domain_skills", ["Instructional Designer"])
        domain_capabilities = reasoning_plan.get("domain_capabilities", [])
        template_id = reasoning_plan.get("template_id", str(uuid.uuid4()))
        
        # Ensure Instructional Designer is always included
        if "Instructional Designer" not in domain_skills:
            domain_skills = ["Instructional Designer"] + domain_skills
        
        prompt = f"""Build a complete domain template for: {instruction}

Domain: {detected_domain}
Template ID: {template_id}
Required Skills: {json.dumps(domain_skills)}
Capability Keys: {json.dumps(domain_capabilities)}

Generate a complete template JSON with:
1. All metadata (created_at, generated_by, session_id)
2. Skills array (MUST include "Instructional Designer")
3. Capabilities object with unique domain-specific keys
4. Templates object with instructional content

Output ONLY valid JSON:"""
        
        result = ""
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            temperature=0.7
        ):
            result += chunk
        
        # Store the template in context metadata
        if "domain_template" not in context.metadata:
            context.metadata["domain_template"] = {}
        
        # Try to parse and validate the JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                template_json = json.loads(json_match.group())
                context.metadata["domain_template"] = template_json
                context.metadata["template_valid"] = True
                return f"Template built successfully:\n{json.dumps(template_json, indent=2)[:1000]}..."
        except json.JSONDecodeError:
            context.metadata["template_valid"] = False
            pass
        
        # Store raw result if JSON parsing fails
        context.metadata["domain_template_raw"] = result
        if "generated_content" not in context.metadata:
            context.metadata["generated_content"] = []
        context.metadata["generated_content"].append(result)
        
        return f"Template generated (raw):\n{result[:500]}..."
    
    async def _action_generate_skills(self, instruction: str, context: AgentContext) -> str:
        """Execute GENERATE_SKILLS action to create domain-specific skills list."""
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        detected_domain = reasoning_plan.get("detected_domain", context.domain)
        base_skills = reasoning_plan.get("domain_skills", [])
        
        prompt = f"""Generate a comprehensive skills list for {detected_domain} domain.

Instruction: {instruction}

MANDATORY: The first skill MUST be "Instructional Designer"

Base skills to include: {json.dumps(base_skills)}

Generate 5-8 domain-specific skills. Output as JSON array:"""
        
        result = ""
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            temperature=0.7
        ):
            result += chunk
        
        # Try to parse skills array
        try:
            json_match = re.search(r'\[[\s\S]*\]', result)
            if json_match:
                skills = json.loads(json_match.group())
                # Ensure Instructional Designer is first
                if "Instructional Designer" not in skills:
                    skills = ["Instructional Designer"] + skills
                elif skills[0] != "Instructional Designer":
                    skills.remove("Instructional Designer")
                    skills = ["Instructional Designer"] + skills
                
                context.metadata["generated_skills"] = skills
                return f"Skills generated:\n{json.dumps(skills, indent=2)}"
        except json.JSONDecodeError:
            pass
        
        # Fallback with base skills
        skills = ["Instructional Designer"] + base_skills
        context.metadata["generated_skills"] = skills
        return f"Skills (using base):\n{json.dumps(skills, indent=2)}"
    
    async def _action_generate_capabilities(self, instruction: str, context: AgentContext) -> str:
        """Execute GENERATE_CAPABILITIES action to create unique capability keys."""
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        detected_domain = reasoning_plan.get("detected_domain", context.domain)
        base_capabilities = reasoning_plan.get("domain_capabilities", [])
        
        prompt = f"""Generate unique capability keys for {detected_domain} domain.

Instruction: {instruction}

Base capability keys: {json.dumps(base_capabilities)}

Requirements:
1. Keys must be unique to this domain (no generic keys)
2. Keys should use snake_case
3. Each key should have a meaningful value describing the capability
4. Generate 4-6 capability key-value pairs

Output as JSON object with capability keys and descriptions:"""
        
        result = ""
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            temperature=0.7
        ):
            result += chunk
        
        # Try to parse capabilities object
        try:
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                capabilities = json.loads(json_match.group())
                context.metadata["generated_capabilities"] = capabilities
                return f"Capabilities generated:\n{json.dumps(capabilities, indent=2)}"
        except json.JSONDecodeError:
            pass
        
        # Fallback with base capabilities as object
        capabilities = {cap: f"Domain-specific {cap} for {detected_domain}" for cap in base_capabilities}
        context.metadata["generated_capabilities"] = capabilities
        return f"Capabilities (using base):\n{json.dumps(capabilities, indent=2)}"
    
    async def _generate_fallback_response(self, context: AgentContext) -> str:
        """Generate a direct response when ReAct loop doesn't produce output."""
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        
        prompt = f"""Generate a comprehensive response for this request.

## USER REQUEST
{context.query}

## PLAN UNDERSTANDING
{reasoning_plan.get('task_understanding', 'Address the user request directly')}

## APPROACH
{reasoning_plan.get('approach', 'Provide helpful, accurate information')}

## CONSTRAINTS
- Be accurate and helpful
- Use clear formatting with headings and bullet points
- Address all aspects of the request
- Provide actionable insights

Generate your response:"""
        
        result = ""
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            temperature=0.7
        ):
            result += chunk
        
        return result
    
    def _extract_scenes(self, content: str, context: AgentContext) -> List[Scene]:
        """Extract structured scenes from the output."""
        scenes = []
        
        # Look for numbered sections - expanded patterns for course content
        patterns = [
            r"(?:Scene|Section|Part|Step|Lesson|Module|Chapter)\s*(\d+)[:\s]+([^\n]+)",
            r"(\d+)\.\s+\*\*([^\*]+)\*\*",
            r"###\s*(\d+)[.:\s]+(.+)",
            r"##\s*(?:Lesson|Module|Chapter)\s*(\d+)[.:\s]+(.+?)(?=\n|$)",
            r"^(\d+)\.\s+(.+?)(?=\n\d+\.|\n##|$)"  # Numbered list items
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            if matches:
                for match in matches[:10]:
                    if len(match) == 2:
                        num, title = match
                        try:
                            scene_num = int(num)
                            scenes.append(Scene(
                                scene_number=scene_num,
                                title=title.strip()[:100],
                                description=f"Content for {title.strip()}",
                                visual_elements=[],
                                camera_direction=""
                            ))
                        except ValueError:
                            continue
                if scenes:
                    break
        
        # If no numbered scenes found, try to extract from headings
        if not scenes:
            heading_pattern = r"^##+\s+(.+?)(?=\n|$)"
            headings = re.findall(heading_pattern, content, re.MULTILINE)
            for idx, heading in enumerate(headings[:10], 1):
                scenes.append(Scene(
                    scene_number=idx,
                    title=heading.strip()[:100],
                    description=f"Content section: {heading.strip()}",
                    visual_elements=[],
                    camera_direction=""
                ))
        
        return scenes
