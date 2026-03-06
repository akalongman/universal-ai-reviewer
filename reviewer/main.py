import sys
from config import Config
from vcs_providers import get_vcs_provider
from prompts import get_code_diff, get_custom_rules, build_prompts
from llm_providers import get_provider


def main():
    # 1. Setup Configuration
    print("Initializing environment and detecting platform...")
    try:
        config = Config()
    except Exception as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

    # 2. Connect to the detected VCS (GitLab/GitHub)
    print(f"Connecting to {config.vcs_type.capitalize()}...")
    try:
        vcs_client = get_vcs_provider(config)
        pr_details = vcs_client.get_mr_details()
    except Exception as e:
        print(f"Error connecting to VCS: {e}")
        sys.exit(1)

    # 3. Read local diff and project rules
    diff = get_code_diff()
    custom_rules = get_custom_rules()

    # 4. Create Real-Time UI Indicator
    thinking_note = None
    try:
        print(f"Creating placeholder comment for {config.provider.capitalize()}...")
        thinking_note = vcs_client.create_placeholder_comment(config.provider)
    except Exception as e:
        print(f"Warning: Could not create placeholder comment: {e}")

    # 5. Request Review from AI Provider
    print(f"Analyzing code with {config.provider.capitalize()}...")
    try:
        system_prompt, user_prompt = build_prompts(
            diff,
            pr_details["title"],
            pr_details["description"],
            custom_rules
        )

        ai_provider = get_provider(config.provider)
        api_key = config.gemini_api_key if config.provider == "gemini" else config.anthropic_api_key

        review_text = ai_provider.review(system_prompt, user_prompt, api_key, config)

        if not review_text:
            raise ValueError(f"{config.provider.capitalize()} returned an empty response.")

    except Exception as e:
        error_msg = f"❌ **AI Review Failed:** {str(e)}"
        print(error_msg)
        if thinking_note:
            vcs_client.update_or_create_comment(thinking_note, error_msg, config.provider)
        sys.exit(1)

    # 6. Post Final Results back to the PR/MR
    print("Updating Pull/Merge Request with final review...")
    try:
        vcs_client.update_or_create_comment(thinking_note, review_text, config.provider)
        print("Review posted successfully!")
    except Exception as e:
        print(f"Error updating comment: {e}")
        sys.exit(1)

    # 7. Status Gatekeeper
    if "🔴 Critical Issues" in review_text:
        print("\n[!] CRITICAL ISSUES DETECTED. Marking job as FAILED.")
        sys.exit(1)
    else:
        print("\n[✓] No critical issues found. Marking job as PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
