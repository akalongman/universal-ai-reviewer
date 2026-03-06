import os
import sys


class Config:
    def __init__(self):
        # 1. AI Provider Setup
        self.provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")

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

        # Validate AI Provider
        if self.provider == "anthropic" and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        elif self.provider == "gemini" and not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")

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
