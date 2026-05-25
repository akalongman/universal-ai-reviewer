import os
import sys


_TRUTHY = {"true", "1", "yes"}
_KNOWN_PROVIDERS = ("anthropic", "gemini", "openai")


def _env_bool(name: str) -> bool:
    value = os.environ.get(name)
    return bool(value) and value.strip().lower() in _TRUTHY


class Config:
    def __init__(self):
        # 1. AI Provider Setup
        self.provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")

        if os.environ.get("AI_MODEL"):
            self.model_name = os.environ.get("AI_MODEL")
        else:
            if self.provider == "anthropic":
                self.model_name = "claude-sonnet-4-6"
            elif self.provider == "gemini":
                self.model_name = "gemini-2.5-pro"
            elif self.provider == "openai":
                self.model_name = "gpt-4o"
            else:
                print(
                    f"Error: Unknown AI_PROVIDER '{self.provider}'. "
                    "Expected one of: anthropic, gemini, openai. "
                    "Set AI_MODEL explicitly when using a custom provider name."
                )
                sys.exit(1)


        self.max_tokens = int(os.environ.get("AI_MAX_TOKENS", "8192"))

        temperature_env = os.environ.get("AI_TEMPERATURE")
        self.temperature = float(temperature_env) if temperature_env else None

        self.fetch_changed_full = _env_bool("AI_FETCH_CHANGED_FULL")
        self.fetch_related_files = _env_bool("AI_FETCH_RELATED_FILES")
        self.fetch_related_depth = self._parse_depth(os.environ.get("AI_FETCH_RELATED_DEPTH"))

        # 2. Auto-Detect the CI/CD Environment
        self.vcs_type = self._detect_vcs()

        # 3. Initialize VCS Variables
        self.gitlab_token = None
        self.ci_server_url = None
        self.ci_project_id = None
        self.ci_merge_request_iid = None

        self.github_token = None
        self.github_repository = None
        self.github_event_path = None

        self._load_vcs_vars()
        self._validate()

    @staticmethod
    def _parse_depth(raw):
        if raw is None or raw == "":
            return 1
        try:
            depth = int(raw)
        except ValueError:
            print(f"Error: AI_FETCH_RELATED_DEPTH must be a non negative integer, got: {raw!r}")
            sys.exit(1)
        if depth < 0:
            print(f"Error: AI_FETCH_RELATED_DEPTH must be a non negative integer, got: {depth}")
            sys.exit(1)
        return depth

    def _detect_vcs(self):
        """Determines the hosting platform based on default runner variables."""
        if os.environ.get("GITLAB_CI"):
            return "gitlab"
        elif os.environ.get("GITHUB_ACTIONS"):
            return "github"
        else:
            # Fallback for local Ubuntu testing
            return os.environ.get("VCS_PROVIDER", "gitlab").lower()

    def _load_vcs_vars(self):
        """Loads only the variables relevant to the detected platform."""
        if self.vcs_type == "gitlab":
            self.gitlab_token = os.environ.get("GITLAB_TOKEN")
            self.ci_server_url = os.environ.get("CI_SERVER_URL", "https://gitlab.com")
            self.ci_project_id = os.environ.get("CI_PROJECT_ID")
            self.ci_merge_request_iid = os.environ.get("CI_MERGE_REQUEST_IID")

        elif self.vcs_type == "github":
            self.github_token = os.environ.get("GITHUB_TOKEN")
            self.github_repository = os.environ.get("GITHUB_REPOSITORY")
            # GitHub stores PR metadata in a temporary JSON file on the runner
            self.github_event_path = os.environ.get("GITHUB_EVENT_PATH")

    def _validate(self):
        """Ensures the environment is fully equipped before starting."""
        missing = []

        # Validate AI Provider name itself. Catches the bypass path where the
        # user sets AI_PROVIDER=<unknown> AND AI_MODEL=<anything>, which would
        # otherwise sail through __init__'s model picker and surface downstream
        # as a confusing SDK error.
        if self.provider not in _KNOWN_PROVIDERS:
            print(
                f"Error: Unsupported AI_PROVIDER {self.provider!r}. "
                f"Expected one of: {', '.join(_KNOWN_PROVIDERS)}."
            )
            sys.exit(1)

        # Validate AI Provider API key
        if self.provider == "anthropic" and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        elif self.provider == "gemini" and not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        elif self.provider == "openai" and not self.openai_api_key:
            missing.append("OPENAI_API_KEY")

        # Validate Platform-Specific Variables
        if self.vcs_type == "gitlab":
            for attr, env_var in [
                (self.gitlab_token, "GITLAB_TOKEN"),
                (self.ci_project_id, "CI_PROJECT_ID"),
                (self.ci_merge_request_iid, "CI_MERGE_REQUEST_IID")
            ]:
                if not attr:
                    missing.append(env_var)

        elif self.vcs_type == "github":
            for attr, env_var in [
                (self.github_token, "GITHUB_TOKEN"),
                (self.github_repository, "GITHUB_REPOSITORY"),
                (self.github_event_path, "GITHUB_EVENT_PATH")
            ]:
                if not attr:
                    missing.append(env_var)
        else:
            print(f"Error: Unsupported VCS provider '{self.vcs_type}'")
            sys.exit(1)

        if missing:
            print(f"Error: Missing required environment variables: {', '.join(missing)}")
            sys.exit(1)

    @property
    def active_api_key(self):
        """Return the API key for the configured AI provider.

        Centralised here so orchestration code never has to know which provider
        name maps to which key attribute. `_validate` rejects unknown providers
        at Config init, so by the time this property runs `self.provider` is
        guaranteed to be one of the three known values.
        """
        if self.provider == "anthropic":
            return self.anthropic_api_key
        if self.provider == "gemini":
            return self.gemini_api_key
        return self.openai_api_key
