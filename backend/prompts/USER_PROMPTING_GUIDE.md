# User Prompting Guide for ReAct/PreAct/REFLECT Models

A comprehensive guide to effectively prompt AI models trained with ReAct, PreAct, and REFLECT techniques.

## Table of Contents

1. [Understanding the Techniques](#understanding-the-techniques)
2. [When to Use Each Technique](#when-to-use-each-technique)
3. [Prompt Formats: Natural Language vs JSON](#prompt-formats)
4. [Trigger Phrases and Keywords](#trigger-phrases)
5. [Prompt Templates](#prompt-templates)
6. [Best Practices](#best-practices)
7. [Domain-Specific Guidance](#domain-specific-guidance)
8. [Troubleshooting](#troubleshooting)
9. [Quick Reference](#quick-reference)

---

## Understanding the Techniques

### ReAct (Reasoning + Acting)

**What it does:** The model alternates between thinking and acting in explicit cycles.

**Pattern:**
```
Thought: What I'm considering...
Action: What I'll do...
Observation: What I learned...
(repeat until complete)
```

**Best for:**
- Debugging and troubleshooting
- Step-by-step problem solving
- Tasks requiring investigation
- Multi-step analysis

**Example output:**
```
Thought: The function returns None, so I should check if there's a return statement.
Action: Analyze the function body for return statements.
Observation: The function has the logic but is missing 'return' keyword.

Thought: I've identified the issue. Now I need to provide the fix.
Action: Add the return statement to the function.
Observation: The corrected function now returns the expected value.

Final Answer: Add 'return reversed_s' at the end of the function.
```

---

### PreAct (Planning Before Acting)

**What it does:** The model creates a complete plan before any execution.

**Pattern:**
```
Plan:
1. Step 1: [what to do] → [expected output]
2. Step 2: [what to do] → [expected output]
   (depends on: Step 1)
3. Step 3: [what to do] → [expected output]
   (depends on: Steps 1, 2)

Ready for execution.
```

**Best for:**
- Project planning
- Course/content creation
- System design
- Complex multi-step tasks
- Tasks with dependencies

**Example output:**
```
## Master Plan: Todo Application

### Step 1: Define Component Structure
- Expected output: List of React components needed
- Dependencies: None

### Step 2: Design State Management
- Expected output: State structure and update functions
- Dependencies: Step 1 (need to know components)

### Step 3: Implement Core Components
- Expected output: Working component code
- Dependencies: Steps 1, 2

### Step 4: Add Styling
- Expected output: Styled application
- Dependencies: Step 3

Plan complete. Ready for execution.
```

---

### REFLECT (Self-Review and Improvement)

**What it does:** The model reviews its own output, critiques it, and provides an improved version.

**Pattern:**
```
Initial Response: [first attempt]

Self-Critique:
- What I did well: ...
- What I missed: ...
- What could be improved: ...

Refined Response: [improved version]
```

**Best for:**
- Code review
- Security audits
- Quality assurance
- Content refinement
- Critical analysis

**Example output:**
```
## Initial Review
The code has a SQL injection vulnerability in the query construction.

## Self-Critique
- Did well: Identified the obvious SQL injection
- Missed: Also storing passwords in plaintext, weak JWT secret
- Could improve: Should check cookie security settings

## Refined Assessment
Critical vulnerabilities found:
1. SQL Injection (Critical) - Use parameterized queries
2. Plaintext passwords (Critical) - Use bcrypt hashing
3. Weak JWT secret (High) - Use environment variable
4. Missing httpOnly cookie flag (Medium) - Add security flags
```

---

## When to Use Each Technique

| Scenario | Recommended Technique | Why |
|----------|----------------------|-----|
| Debug a bug | ReAct | Need iterative investigation |
| Plan a project | PreAct | Need upfront structure |
| Review code/content | REFLECT | Need quality improvement |
| Design a system | PreAct → ReAct | Plan first, then detail |
| Security audit | REFLECT | Need thorough critique |
| Learn/explain concept | ReAct | Step-by-step breakdown |
| Create course content | PreAct → ReAct → REFLECT | Full pipeline |
| Quick question | None (auto) | Simple response sufficient |

### Decision Flowchart

```
Is the task complex (3+ steps)?
├── No → Use natural prompt (no technique trigger)
└── Yes → Continue...
    │
    Does it need upfront planning?
    ├── Yes → Use PreAct
    │   └── Also need detailed execution? → Add ReAct
    └── No → Continue...
        │
        Is it investigation/debugging?
        ├── Yes → Use ReAct
        └── No → Continue...
            │
            Does it need quality review?
            ├── Yes → Use REFLECT
            └── No → Use ReAct (default for complex)
```

---

## Prompt Formats

### Natural Language (Recommended for Most Users)

Use natural language when:
- You're exploring or asking questions
- The task is straightforward
- You don't need programmatic parsing of output
- You want conversational interaction

**Structure:**
```
Task: [What you want done]

Context: [Background information]

Requirements:
- [Specific requirement 1]
- [Specific requirement 2]

[Technique trigger phrase]

Expected Output: [What format you want]
```

### JSON Format (For Programmatic Use)

Use JSON when:
- Building automated pipelines
- Need consistent, parseable output
- Complex tasks with many parameters
- API integrations

**Structure:**
```json
{
  "task": {
    "type": "design|analyze|create|debug|optimize",
    "objective": "Clear description of goal",
    "domain": "software|education|healthcare|finance|marketing|legal"
  },
  "context": {
    "background": "Relevant context",
    "constraints": ["constraint1", "constraint2"],
    "existing_state": "Current situation"
  },
  "requirements": {
    "functional": ["what it must do"],
    "non_functional": ["how it must perform"],
    "output_format": "Expected structure"
  },
  "thinking_mode": {
    "technique": "react|preact|reflect|combined",
    "show_reasoning": true,
    "iteration_count": 2
  }
}
```

---

## Trigger Phrases

### ReAct Triggers
Use these phrases to activate Thought-Action-Observation reasoning:

- "Think through this step-by-step"
- "Explain your reasoning at each stage"
- "Show your thought process"
- "What actions would you take and why?"
- "Work through this methodically"
- "Analyze and act on each step"
- "Use the Thought-Action-Observation pattern"

**Example:**
```
Debug this memory leak. Think through this step-by-step, 
showing your Thought → Action → Observation for each 
investigation step.
```

### PreAct Triggers
Use these phrases to activate upfront planning:

- "Create a plan first"
- "Outline your approach before starting"
- "What strategy would work best?"
- "Design a structured plan"
- "Break this into actionable steps"
- "Create a master plan for this task"
- "Plan the execution sequence first"

**Example:**
```
Build a user authentication system. Before you start coding,
create a comprehensive plan with numbered steps, dependencies,
and expected outputs for each step.
```

### REFLECT Triggers
Use these phrases to activate self-review:

- "Review your answer for issues"
- "Critique your solution"
- "Identify potential problems"
- "What could be improved?"
- "Check for consistency and errors"
- "Refine and enhance your output"
- "Validate your approach"

**Example:**
```
Review this API design for security issues. After your initial
analysis, critique your own review to catch anything you missed,
then provide a final refined assessment.
```

### Combined Triggers
Use these to activate the full pipeline:

- "Plan first, then execute step-by-step, and finally review"
- "Approach this systematically: plan, execute, reflect"
- "Create a plan, work through it with reasoning, then critique"

**Example:**
```
Design a notification system.

Phase 1: Create a comprehensive plan (PreAct)
Phase 2: Work through implementation step-by-step (ReAct)  
Phase 3: Review for issues and improvements (REFLECT)
```

---

## Prompt Templates

### Minimal Prompt (Low Effectiveness)
```
[Just the task]
```
Example: `Sort a list of dictionaries by key`

### Basic Structured Prompt (Medium Effectiveness)
```
Task: [Clear task description]

Context: [Relevant background]

Please provide a detailed response.
```

### Optimal ReAct Prompt (High Effectiveness)
```
Task: [Task description]

Context: [Background information]

Requirements:
- [Requirement 1]
- [Requirement 2]

Please think through this step-by-step. For each step:
1. State what you're thinking about (Thought)
2. Decide what action to take (Action)
3. Explain what you learned (Observation)

Continue until the task is complete.
```

### Optimal PreAct Prompt (High Effectiveness)
```
Task: [Task description]

Context: [Background information]

Before executing, please:
1. Create a comprehensive plan with numbered steps
2. Define what each step should produce
3. Identify dependencies between steps
4. Set success criteria for each step

Output the plan first, then indicate you're ready for execution.
```

### Optimal REFLECT Prompt (High Effectiveness)
```
Task: [Task description]

Context: [Background information]

After completing your response, please:
1. Review your answer for accuracy and completeness
2. Check for logical consistency
3. Identify any gaps or potential issues
4. Suggest improvements or alternatives
5. Provide a final refined version if needed

Structure: Initial Response → Self-Critique → Refined Response
```

### Full Pipeline Prompt (Highest Effectiveness)
```
Task: [Complex task description]

Context: [Background information]

Requirements:
- [Requirement 1]
- [Requirement 2]

Please approach this systematically:

## Phase 1: Planning (PreAct)
Create a detailed execution plan with steps, dependencies, 
and success criteria.

## Phase 2: Execution (ReAct)
Work through your plan step-by-step, showing:
- Thought: What you're considering
- Action: What you'll do
- Observation: What you learned

## Phase 3: Review (REFLECT)
Review your complete output:
- Check for errors or inconsistencies
- Identify improvements
- Provide the final polished version

Format your response with clear section headers.
```

---

## Best Practices

### DO:

1. **Be Specific**
   - Bad: "Make a website"
   - Good: "Create a landing page for a SaaS product with hero section, features, and pricing"

2. **Provide Context**
   - Bad: "Fix this code"
   - Good: "Fix this Python function that should return the sum but returns None. It's used in a financial calculation module."

3. **Set Constraints**
   - "Limit response to 500 words"
   - "Use only Python 3.10+ features"
   - "Assume no prior programming knowledge"

4. **Specify Output Format**
   - "Provide the answer as a numbered list"
   - "Structure with Executive Summary, Details, and Recommendations"
   - "Include code examples with comments"

5. **Request Explanations**
   - "Explain why this approach is best"
   - "Show your reasoning"
   - "Justify your recommendations"

### DON'T:

1. **Don't Be Vague**
   - Bad: "Help me with my project"
   - Good: "Help me design the database schema for a blog with posts, comments, and user authentication"

2. **Don't Overload**
   - Bad: Combining 5 unrelated tasks in one prompt
   - Good: One focused task per prompt, or clearly numbered separate tasks

3. **Don't Skip Context**
   - Bad: "Why is this slow?"
   - Good: "This SQL query takes 30 seconds on a table with 1M rows. Why is it slow? [query here]"

4. **Don't Assume Knowledge**
   - Provide relevant code snippets
   - Explain your tech stack
   - Mention constraints and requirements

---

## Domain-Specific Guidance

### Software Development
```
Task: [Technical task]

Technical Context:
- Tech Stack: [languages, frameworks]
- Architecture: [monolith, microservices, etc.]
- Constraints: [performance, security, etc.]

Requirements:
[List specific requirements]

Please think through this step-by-step, considering:
- Best practices
- Error handling
- Maintainability
- Security implications
```

### Education/Training
```
Learning Objective: [What learners should achieve]

Target Audience:
- Level: [beginner, intermediate, advanced]
- Prerequisites: [required knowledge]
- Learning Style: [hands-on, conceptual, etc.]

Content Requirements:
[Specific content needs]

Create content that builds progressively. Plan the structure 
first, then develop each section.
```

### Healthcare (Always Include Disclaimers)
```
Topic: [Health-related topic]

Context:
- Setting: [clinical, patient education, etc.]
- Audience: [patients, providers, etc.]
- Purpose: [education, guidance, etc.]

Requirements:
[Specific information needs]

IMPORTANT: Include appropriate disclaimers. Prioritize accuracy 
and patient safety. Review your response for accuracy.

Note: This is for educational purposes only and should not 
replace professional medical advice.
```

### Finance (Always Include Disclaimers)
```
Objective: [Financial analysis goal]

Context:
- Market/Sector: [relevant markets]
- Time Horizon: [investment period]
- Risk Profile: [conservative, moderate, aggressive]

Analysis Requirements:
[Specific analysis needs]

Show your analytical reasoning step-by-step. Include appropriate 
risk disclosures.

Note: This is for informational purposes only and does not 
constitute financial advice.
```

---

## Troubleshooting

### Problem: Model Not Using Expected Technique

**Symptoms:** You asked for step-by-step reasoning but got a direct answer.

**Solutions:**
1. Make trigger phrases more explicit
2. Add format instructions: "Format as Thought: / Action: / Observation:"
3. Provide an example of expected output format

### Problem: Plan Too Shallow

**Symptoms:** PreAct plan lacks detail or dependencies.

**Solutions:**
1. Request specific elements: "Include dependencies, expected outputs, and success criteria"
2. Specify number of steps: "Create a plan with at least 5 detailed steps"
3. Ask for timeline estimates

### Problem: Reflection Not Critical Enough

**Symptoms:** Self-critique is superficial or just validates the original.

**Solutions:**
1. Explicitly request: "Identify at least 3 potential issues"
2. Add persona: "Critique this as a senior engineer would"
3. Provide evaluation criteria

### Problem: Output Too Long/Short

**Symptoms:** Response length doesn't match needs.

**Solutions:**
1. Set explicit limits: "Keep response under 500 words"
2. Request structure: "Provide executive summary then details"
3. Specify depth: "High-level overview only" or "Detailed implementation"

### Problem: Missing Important Elements

**Symptoms:** Response doesn't cover all requirements.

**Solutions:**
1. Use numbered requirements that must all be addressed
2. Add: "Confirm you've addressed all requirements before finishing"
3. Request checklist in output

---

## Quick Reference

### Technique Selection
| Task Type | Use This | Trigger |
|-----------|----------|---------|
| Debug/Investigate | ReAct | "step-by-step" |
| Plan/Design | PreAct | "plan first" |
| Review/Improve | REFLECT | "review and refine" |
| Complex Project | All Three | "plan, execute, reflect" |

### Essential Trigger Phrases
- **ReAct:** "Think through this step-by-step"
- **PreAct:** "Create a plan before starting"
- **REFLECT:** "Review and critique your answer"
- **Combined:** "Plan first, then execute, then review"

### Prompt Quality Checklist
- [ ] Clear task description
- [ ] Relevant context provided
- [ ] Specific requirements listed
- [ ] Technique trigger included
- [ ] Output format specified
- [ ] Constraints defined

### Output Format Requests
- Structured: "Use sections with headers"
- Code-focused: "Include working code with comments"
- Comparison: "Provide pros/cons comparison"
- Tutorial: "Step-by-step guide format"

---

## Examples Repository

For ready-to-use test prompts across all techniques and domains, see:
- `prompt_test_cases.json` - 20 test cases with expected behaviors
- `user_prompt_templates.json` - Template library for all scenarios

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-12-26 | Initial release |








