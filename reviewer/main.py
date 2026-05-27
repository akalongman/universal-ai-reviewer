import sys
from config import Config
from vcs_providers import get_vcs_provider
from prompts import (
    get_code_diff,
    get_custom_rules,
    build_prompts,
    get_ignore_patterns,
    gatekeeper_exit_code,
)
from llm_providers import get_provider
from context_fetcher import ContextFetcher, check_context_window


def main():
    # 1. Setup Configuration
    print("Initializing environment and detecting platform...")
    try:
        config = Config()
    except Exception as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

    print("\n" + "=" * 35)
    print("🔧 AI RUNTIME CONFIGURATION")
    print("=" * 35)
    print(f"VCS Platform   : {config.vcs_type.upper()}")
    print(f"AI Provider    : {config.provider.upper()}")
    print(f"AI Model       : {config.model_name}")
    print(f"Max Tokens     : {config.max_tokens}")
    print(f"Temperature    : {config.temperature if config.temperature is not None else '(provider default)'}")
    print(f"Fetch Changed  : {config.fetch_changed_full}")
    print(f"Fetch Related  : {config.fetch_related_files} (depth={config.fetch_related_depth})")
    print("=" * 35 + "\n")


    # 2. Connect to the detected VCS (GitLab/GitHub)
    print(f"Connecting to {config.vcs_type.capitalize()}...")
    try:
        vcs_client = get_vcs_provider(config)
        pr_details = vcs_client.get_mr_details()
    except Exception as e:
        print(f"Error connecting to VCS: {e}")
        sys.exit(1)

    # 3. Read local diff and project rules
    ignore_patterns = get_ignore_patterns()
    diff = get_code_diff(ignore_patterns=ignore_patterns)
    custom_rules = get_custom_rules()

    # 4. Create a Real-Time UI Indicator
    thinking_note = None
    fetch_enabled = config.fetch_changed_full or config.fetch_related_files
    extra_text = "(Fetching file context...)" if fetch_enabled else ""
    try:
        print(f"Creating placeholder comment for {config.provider.capitalize()}...")
        thinking_note = vcs_client.create_placeholder_comment(config.provider, extra=extra_text)
    except Exception as e:
        print(f"Warning: Could not create placeholder comment: {e}")

    # 5. Fetch full file context (skipped entirely when both fetch env vars are off)
    fetched_files = None
    if fetch_enabled:
        try:
            fetcher = ContextFetcher(vcs_client, config, ignore_patterns)
            fetched_files = fetcher.fetch_for_diff(diff)
            print(f"Fetched {len(fetched_files)} file(s) of additional context.")
        except Exception as e:
            error_msg = f"❌ **Context Fetch Failed:** {str(e)}"
            print(error_msg)
            if thinking_note:
                vcs_client.update_or_create_comment(thinking_note, error_msg, config.provider)
            sys.exit(1)

    # 6. Request Review from AI Provider
    print(f"Analyzing code with {config.provider.capitalize()}...")
    try:
        system_prompt, user_prompt = build_prompts(
            diff,
            pr_details["title"],
            pr_details["description"],
            custom_rules,
            fetched_files=fetched_files,
        )

        check_context_window(system_prompt, user_prompt, config.model_name)

        ai_provider = get_provider(config.provider)
        review_text = ai_provider.review(system_prompt, user_prompt, config.active_api_key, config)

        if not review_text:
            raise ValueError(f"{config.provider.capitalize()} returned an empty response.")

    except Exception as e:
        error_msg = f"❌ **AI Review Failed:** {str(e)}"
        print(error_msg)
        if thinking_note:
            vcs_client.update_or_create_comment(thinking_note, error_msg, config.provider)
        sys.exit(1)

    # 7. Post Final Results back to the PR/MR
    print("Updating Pull/Merge Request with final review...")
    try:
        vcs_client.update_or_create_comment(thinking_note, review_text, config.provider)
        print("Review posted successfully!")
    except Exception as e:
        print(f"Error updating comment: {e}")
        sys.exit(1)

    # 8. Status Gatekeeper
    print()
    sys.exit(gatekeeper_exit_code(review_text))

if __name__ == "__main__":
    main()
