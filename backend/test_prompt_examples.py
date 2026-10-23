"""
Test script for ReAct/PreAct/REFLECT prompt templates.

This script provides utilities to:
- Load and execute test cases from prompt_test_cases.json
- Format prompts using templates from user_prompt_templates.json
- Test prompts against the LLM service
- Evaluate responses based on technique activation

Usage:
    # Run all tests
    python test_prompt_examples.py --all
    
    # Run specific test case
    python test_prompt_examples.py --test TC001
    
    # Run tests by category
    python test_prompt_examples.py --difficulty simple
    python test_prompt_examples.py --technique react
    python test_prompt_examples.py --domain software
    
    # Interactive mode
    python test_prompt_examples.py --interactive
    
    # List all test cases
    python test_prompt_examples.py --list
"""

import asyncio
import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Try to import LLM service (may fail if dependencies not installed)
try:
    from services.llm import LLMService, get_llm_service
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("Warning: LLM service not available. Running in template-only mode.")


class PromptTester:
    """
    Utility class for testing prompts against ReAct/PreAct/REFLECT models.
    """
    
    def __init__(self, templates_path: str = None, test_cases_path: str = None):
        """
        Initialize the prompt tester.
        
        Args:
            templates_path: Path to user_prompt_templates.json
            test_cases_path: Path to prompt_test_cases.json
        """
        self.base_path = Path(__file__).parent / "prompts"
        self.templates_path = templates_path or self.base_path / "user_prompt_templates.json"
        self.test_cases_path = test_cases_path or self.base_path / "prompt_test_cases.json"
        
        self.templates = self._load_json(self.templates_path)
        self.test_cases = self._load_json(self.test_cases_path)
        
        self.llm = get_llm_service() if LLM_AVAILABLE else None
        self.results: List[Dict[str, Any]] = []
    
    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: {path} not found.")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing {path}: {e}")
            return {}
    
    def list_test_cases(self) -> None:
        """Print all available test cases."""
        print("\n" + "=" * 80)
        print("AVAILABLE TEST CASES")
        print("=" * 80 + "\n")
        
        for case in self.test_cases.get("test_cases", []):
            print(f"ID: {case['id']}")
            print(f"  Name: {case['name']}")
            print(f"  Difficulty: {case['difficulty']}")
            print(f"  Technique: {case['target_technique']}")
            print(f"  Domain: {case['domain']}")
            print()
    
    def list_templates(self) -> None:
        """Print available prompt templates."""
        print("\n" + "=" * 80)
        print("AVAILABLE TEMPLATES")
        print("=" * 80 + "\n")
        
        # Natural language templates
        print("NATURAL LANGUAGE TEMPLATES:")
        for name, template in self.templates.get("natural_language_templates", {}).items():
            print(f"  - {name}: {template.get('description', 'No description')}")
        
        print("\nJSON STRUCTURED TEMPLATES:")
        for name, template in self.templates.get("json_structured_templates", {}).items():
            print(f"  - {name}: {template.get('description', 'No description')}")
        
        print("\nDOMAIN-SPECIFIC TEMPLATES:")
        for name in self.templates.get("domain_specific_templates", {}).keys():
            print(f"  - {name}")
    
    def get_test_case(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific test case by ID."""
        for case in self.test_cases.get("test_cases", []):
            if case["id"] == test_id:
                return case
        return None
    
    def get_test_cases_by_category(
        self,
        difficulty: Optional[str] = None,
        technique: Optional[str] = None,
        domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get test cases filtered by category.
        
        Args:
            difficulty: Filter by difficulty (simple, medium, complex)
            technique: Filter by technique (react, preact, reflect, combined)
            domain: Filter by domain (software, education, etc.)
            
        Returns:
            List of matching test cases
        """
        categories = self.test_cases.get("test_categories", {})
        
        # Get IDs for each filter
        matching_ids = None
        
        if difficulty:
            diff_ids = set(categories.get("by_difficulty", {}).get(difficulty, []))
            matching_ids = diff_ids if matching_ids is None else matching_ids & diff_ids
        
        if technique:
            tech_ids = set(categories.get("by_technique", {}).get(technique, []))
            matching_ids = tech_ids if matching_ids is None else matching_ids & tech_ids
        
        if domain:
            domain_ids = set(categories.get("by_domain", {}).get(domain, []))
            matching_ids = domain_ids if matching_ids is None else matching_ids & domain_ids
        
        if matching_ids is None:
            return self.test_cases.get("test_cases", [])
        
        return [
            case for case in self.test_cases.get("test_cases", [])
            if case["id"] in matching_ids
        ]
    
    def format_prompt(
        self,
        template_name: str,
        template_category: str = "natural_language_templates",
        **kwargs
    ) -> str:
        """
        Format a prompt using a template.
        
        Args:
            template_name: Name of the template
            template_category: Category of the template
            **kwargs: Variables to substitute in the template
            
        Returns:
            Formatted prompt string
        """
        templates = self.templates.get(template_category, {})
        template = templates.get(template_name, {})
        
        template_str = template.get("template", "")
        
        # Substitute variables
        for key, value in kwargs.items():
            if isinstance(value, list):
                value = "\n".join(f"- {item}" for item in value)
            template_str = template_str.replace(f"{{{key}}}", str(value))
        
        return template_str
    
    def get_trigger_phrases(self, technique: str) -> List[str]:
        """Get trigger phrases for a specific technique."""
        triggers = self.templates.get("technique_triggers", {})
        return triggers.get(technique, {}).get("key_phrases", [])
    
    def analyze_response(
        self,
        response: str,
        expected_technique: str
    ) -> Dict[str, Any]:
        """
        Analyze a response to check if the expected technique was activated.
        
        Args:
            response: Model response
            expected_technique: Expected technique (react, preact, reflect)
            
        Returns:
            Analysis results
        """
        analysis = {
            "technique_detected": None,
            "confidence": 0.0,
            "indicators_found": [],
            "score": 0
        }
        
        response_lower = response.lower()
        
        # ReAct indicators
        react_indicators = [
            ("thought:", 3),
            ("action:", 3),
            ("observation:", 3),
            ("thinking:", 2),
            ("step-by-step", 1),
            ("let me think", 1),
            ("first, i'll", 1),
            ("next, i'll", 1)
        ]
        
        # PreAct indicators
        preact_indicators = [
            ("plan:", 3),
            ("step 1:", 2),
            ("step 2:", 2),
            ("master plan", 3),
            ("before executing", 2),
            ("dependencies:", 2),
            ("expected output:", 2),
            ("success criteria:", 2)
        ]
        
        # REFLECT indicators
        reflect_indicators = [
            ("self-critique", 3),
            ("reviewing:", 2),
            ("initial response:", 2),
            ("refined response:", 2),
            ("what i missed:", 2),
            ("improvements:", 2),
            ("upon reflection", 2),
            ("looking back", 1)
        ]
        
        # Score each technique
        react_score = sum(weight for indicator, weight in react_indicators if indicator in response_lower)
        preact_score = sum(weight for indicator, weight in preact_indicators if indicator in response_lower)
        reflect_score = sum(weight for indicator, weight in reflect_indicators if indicator in response_lower)
        
        # Collect found indicators
        for indicator, _ in react_indicators:
            if indicator in response_lower:
                analysis["indicators_found"].append(f"react: {indicator}")
        for indicator, _ in preact_indicators:
            if indicator in response_lower:
                analysis["indicators_found"].append(f"preact: {indicator}")
        for indicator, _ in reflect_indicators:
            if indicator in response_lower:
                analysis["indicators_found"].append(f"reflect: {indicator}")
        
        # Determine detected technique
        scores = {
            "react": react_score,
            "preact": preact_score,
            "reflect": reflect_score
        }
        
        if max(scores.values()) > 0:
            analysis["technique_detected"] = max(scores, key=scores.get)
            analysis["confidence"] = max(scores.values()) / 15.0  # Normalize to 0-1
        
        # Check if expected technique was activated
        if expected_technique == "combined":
            # For combined, check if multiple techniques are present
            active_techniques = sum(1 for s in scores.values() if s > 3)
            analysis["score"] = min(3, active_techniques)
        elif expected_technique == "auto":
            # For auto, any reasonable response is fine
            analysis["score"] = 2 if len(response) > 100 else 1
        else:
            if analysis["technique_detected"] == expected_technique:
                analysis["score"] = 3 if analysis["confidence"] > 0.5 else 2
            elif scores.get(expected_technique, 0) > 0:
                analysis["score"] = 1
            else:
                analysis["score"] = 0
        
        return analysis
    
    async def run_test(
        self,
        test_case: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run a single test case.
        
        Args:
            test_case: Test case dictionary
            verbose: Print detailed output
            
        Returns:
            Test result dictionary
        """
        if not self.llm:
            return {
                "test_id": test_case["id"],
                "status": "skipped",
                "reason": "LLM service not available"
            }
        
        test_id = test_case["id"]
        prompt = test_case["prompt"]
        expected_technique = test_case["target_technique"]
        
        # Handle JSON prompts
        if isinstance(prompt, dict):
            prompt = json.dumps(prompt, indent=2)
        
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"Running Test: {test_id} - {test_case['name']}")
            print(f"{'=' * 80}")
            print(f"Technique: {expected_technique}")
            print(f"Difficulty: {test_case['difficulty']}")
            print(f"Domain: {test_case['domain']}")
            print(f"\nPrompt:\n{prompt[:500]}{'...' if len(prompt) > 500 else ''}")
        
        try:
            # Get system prompt based on technique
            system_prompts = {
                "react": "You are an AI assistant that uses Thought-Action-Observation reasoning loops.",
                "preact": "You are an AI assistant that creates detailed plans before executing tasks.",
                "reflect": "You are an AI assistant that reviews and refines your responses.",
                "combined": "You are an AI assistant that plans, executes with reasoning, and reviews outputs.",
                "auto": "You are a helpful AI assistant."
            }
            
            system_prompt = system_prompts.get(expected_technique, system_prompts["auto"])
            
            # Generate response
            start_time = datetime.now()
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000
            )
            end_time = datetime.now()
            
            # Analyze response
            analysis = self.analyze_response(response, expected_technique)
            
            result = {
                "test_id": test_id,
                "status": "completed",
                "expected_technique": expected_technique,
                "detected_technique": analysis["technique_detected"],
                "technique_score": analysis["score"],
                "confidence": analysis["confidence"],
                "indicators_found": analysis["indicators_found"],
                "response_length": len(response),
                "duration_ms": (end_time - start_time).total_seconds() * 1000,
                "success_criteria": test_case.get("success_criteria", []),
                "response_preview": response[:500]
            }
            
            if verbose:
                print(f"\nResponse Preview:\n{response[:500]}{'...' if len(response) > 500 else ''}")
                print(f"\n{'─' * 40}")
                print(f"Analysis:")
                print(f"  Detected Technique: {analysis['technique_detected']}")
                print(f"  Confidence: {analysis['confidence']:.2f}")
                print(f"  Score: {analysis['score']}/3")
                print(f"  Indicators: {', '.join(analysis['indicators_found'][:5])}")
            
            return result
            
        except Exception as e:
            return {
                "test_id": test_id,
                "status": "error",
                "error": str(e)
            }
    
    async def run_tests(
        self,
        test_cases: List[Dict[str, Any]],
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Run multiple test cases.
        
        Args:
            test_cases: List of test cases
            verbose: Print detailed output
            
        Returns:
            List of test results
        """
        results = []
        
        for case in test_cases:
            result = await self.run_test(case, verbose)
            results.append(result)
            self.results.append(result)
        
        return results
    
    def print_summary(self, results: List[Dict[str, Any]] = None) -> None:
        """Print summary of test results."""
        results = results or self.results
        
        if not results:
            print("No results to summarize.")
            return
        
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80 + "\n")
        
        completed = [r for r in results if r["status"] == "completed"]
        errors = [r for r in results if r["status"] == "error"]
        skipped = [r for r in results if r["status"] == "skipped"]
        
        print(f"Total Tests: {len(results)}")
        print(f"Completed: {len(completed)}")
        print(f"Errors: {len(errors)}")
        print(f"Skipped: {len(skipped)}")
        
        if completed:
            avg_score = sum(r["technique_score"] for r in completed) / len(completed)
            correct_technique = sum(
                1 for r in completed 
                if r["detected_technique"] == r["expected_technique"]
            )
            
            print(f"\nAverage Technique Score: {avg_score:.2f}/3")
            print(f"Correct Technique Detection: {correct_technique}/{len(completed)}")
        
        print("\n" + "─" * 40)
        print("Individual Results:")
        for r in results:
            status_icon = "✓" if r["status"] == "completed" else "✗" if r["status"] == "error" else "○"
            score = r.get("technique_score", "N/A")
            print(f"  {status_icon} {r['test_id']}: Score {score}/3 - {r['status']}")
    
    def save_results(self, filepath: str = None) -> None:
        """Save results to JSON file."""
        filepath = filepath or f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.results),
                "results": self.results
            }, f, indent=2)
        
        print(f"\nResults saved to: {filepath}")


async def interactive_mode(tester: PromptTester) -> None:
    """Run interactive testing mode."""
    print("\n" + "=" * 80)
    print("INTERACTIVE PROMPT TESTING MODE")
    print("=" * 80)
    print("\nCommands:")
    print("  list     - List all test cases")
    print("  run TC001- Run specific test case")
    print("  custom   - Enter custom prompt")
    print("  quit     - Exit interactive mode")
    print()
    
    while True:
        try:
            cmd = input("\n> ").strip()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "list":
                tester.list_test_cases()
            elif cmd.startswith("run "):
                test_id = cmd[4:].strip()
                test_case = tester.get_test_case(test_id)
                if test_case:
                    await tester.run_test(test_case, verbose=True)
                else:
                    print(f"Test case '{test_id}' not found.")
            elif cmd == "custom":
                print("\nEnter your prompt (press Enter twice to submit):")
                lines = []
                while True:
                    line = input()
                    if line == "":
                        break
                    lines.append(line)
                
                if lines:
                    prompt = "\n".join(lines)
                    technique = input("Expected technique (react/preact/reflect/auto): ").strip()
                    
                    custom_case = {
                        "id": "CUSTOM",
                        "name": "Custom Test",
                        "prompt": prompt,
                        "target_technique": technique or "auto",
                        "difficulty": "custom",
                        "domain": "general"
                    }
                    
                    await tester.run_test(custom_case, verbose=True)
            else:
                print("Unknown command. Type 'list', 'run TC001', 'custom', or 'quit'.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test ReAct/PreAct/REFLECT prompt templates"
    )
    
    parser.add_argument(
        "--all", action="store_true",
        help="Run all test cases"
    )
    parser.add_argument(
        "--test", type=str,
        help="Run specific test case by ID (e.g., TC001)"
    )
    parser.add_argument(
        "--difficulty", type=str,
        choices=["simple", "medium", "complex"],
        help="Run tests by difficulty"
    )
    parser.add_argument(
        "--technique", type=str,
        choices=["react", "preact", "reflect", "combined", "auto"],
        help="Run tests by technique"
    )
    parser.add_argument(
        "--domain", type=str,
        help="Run tests by domain"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all test cases"
    )
    parser.add_argument(
        "--templates", action="store_true",
        help="List all templates"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--save", type=str,
        help="Save results to file"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Minimal output"
    )
    
    args = parser.parse_args()
    
    tester = PromptTester()
    
    # Handle different modes
    if args.list:
        tester.list_test_cases()
        return
    
    if args.templates:
        tester.list_templates()
        return
    
    if args.interactive:
        await interactive_mode(tester)
        return
    
    # Get test cases to run
    test_cases = []
    
    if args.test:
        case = tester.get_test_case(args.test)
        if case:
            test_cases = [case]
        else:
            print(f"Test case '{args.test}' not found.")
            return
    elif args.all:
        test_cases = tester.test_cases.get("test_cases", [])
    elif args.difficulty or args.technique or args.domain:
        test_cases = tester.get_test_cases_by_category(
            difficulty=args.difficulty,
            technique=args.technique,
            domain=args.domain
        )
    else:
        # Default: show help
        parser.print_help()
        print("\nExamples:")
        print("  python test_prompt_examples.py --list")
        print("  python test_prompt_examples.py --test TC001")
        print("  python test_prompt_examples.py --difficulty simple")
        print("  python test_prompt_examples.py --technique react")
        print("  python test_prompt_examples.py --interactive")
        return
    
    if not test_cases:
        print("No test cases found matching criteria.")
        return
    
    print(f"\nRunning {len(test_cases)} test(s)...")
    
    # Run tests
    verbose = not args.quiet
    results = await tester.run_tests(test_cases, verbose=verbose)
    
    # Print summary
    tester.print_summary(results)
    
    # Save results if requested
    if args.save:
        tester.save_results(args.save)


def print_example_prompts():
    """Print example prompts for quick reference."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        QUICK REFERENCE: EXAMPLE PROMPTS                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  ReAct (Step-by-step reasoning):                                              ║
║  ───────────────────────────────                                              ║
║  "Debug this code. Think through this step-by-step, showing your              ║
║   Thought → Action → Observation for each investigation step."                ║
║                                                                               ║
║  PreAct (Planning first):                                                     ║
║  ─────────────────────────                                                    ║
║  "Build a REST API. Before coding, create a comprehensive plan with           ║
║   numbered steps, dependencies, and expected outputs for each step."          ║
║                                                                               ║
║  REFLECT (Self-review):                                                       ║
║  ──────────────────────                                                       ║
║  "Review this code for security issues. After your initial analysis,          ║
║   critique your own review, then provide a final refined assessment."         ║
║                                                                               ║
║  Combined (Full pipeline):                                                    ║
║  ─────────────────────────                                                    ║
║  "Design a notification system.                                               ║
║   Phase 1: Create a plan (PreAct)                                             ║
║   Phase 2: Implement step-by-step (ReAct)                                     ║
║   Phase 3: Review and improve (REFLECT)"                                      ║
║                                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    # Check if running with no args
    if len(sys.argv) == 1:
        print_example_prompts()
        print("\nRun with --help for usage information.")
        print("Run with --interactive for interactive testing mode.")
    else:
        asyncio.run(main())








