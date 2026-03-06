import os
import sys
import json
from abc import ABC, abstractmethod


class VCSProvider(ABC):
    """Abstract Base Class defining the standard operations for any Code Hosting Platform."""

    @abstractmethod
    def get_mr_details(self) -> dict:
        """Returns a dictionary with 'title' and 'description' keys."""
        pass

    @abstractmethod
    def create_placeholder_comment(self, ai_provider_name: str):
        """Creates a 'Thinking...' comment and returns the comment object."""
        pass

    @abstractmethod
    def update_or_create_comment(self, note, review_text: str, ai_provider_name: str):
        """Updates the placeholder comment with the final review, or creates a new one."""
        pass


# --- GITLAB IMPLEMENTATION ---

class GitLabProvider(VCSProvider):
    def __init__(self, url, token, project_id, mr_iid):
        import gitlab
        self.gl = gitlab.Gitlab(url=url, private_token=token)
        self.project = self.gl.projects.get(project_id)
        self.mr = self.project.mergerequests.get(mr_iid)

    def get_mr_details(self):
        return {
            "title": self.mr.title,
            "description": self.mr.description or "No description provided."
        }

    def create_placeholder_comment(self, ai_provider_name):
        body = f"⏳ **{ai_provider_name.capitalize()} is reviewing your code...**\n*(This usually takes 10-20 seconds)*"
        return self.mr.notes.create({'body': body})

    def update_or_create_comment(self, note, review_text, ai_provider_name):
        final_body = f"### 🤖 AI Code Review ({ai_provider_name.capitalize()})\n\n{review_text}"
        if note:
            note.body = final_body
            note.save()
        else:
            self.mr.notes.create({'body': final_body})


# --- GITHUB IMPLEMENTATION ---

class GitHubProvider(VCSProvider):
    def __init__(self, token, repository, event_path):
        from github import Github
        self.client = Github(token)
        self.repo = self.client.get_repo(repository)

        # GitHub Actions passes the Pull Request context in a local JSON file
        try:
            with open(event_path, 'r') as f:
                event = json.load(f)
                self.pr_number = event['pull_request']['number']
        except (FileNotFoundError, KeyError):
            print(f"Error: Could not parse PR number from GITHUB_EVENT_PATH ({event_path}).")
            sys.exit(1)

        self.pr = self.repo.get_pull(self.pr_number)
        # In GitHub's API, Pull Request comments are treated as Issue comments
        self.issue = self.repo.get_issue(self.pr_number)

    def get_mr_details(self):
        return {
            "title": self.pr.title,
            "description": self.pr.body or "No description provided."
        }

    def create_placeholder_comment(self, ai_provider_name):
        body = f"⏳ **{ai_provider_name.capitalize()} is reviewing your code...**\n*(This usually takes 10-20 seconds)*"
        return self.issue.create_comment(body)

    def update_or_create_comment(self, note, review_text, ai_provider_name):
        final_body = f"### 🤖 AI Code Review ({ai_provider_name.capitalize()})\n\n{review_text}"
        if note:
            note.edit(final_body)
        else:
            self.issue.create_comment(final_body)


# --- FACTORY FUNCTION ---

def get_vcs_provider(config):
    """Instantiates the correct provider based on the detected environment."""
    if config.vcs_type == "gitlab":
        return GitLabProvider(
            url=config.ci_server_url,
            token=config.gitlab_token,
            project_id=config.ci_project_id,
            mr_iid=config.ci_merge_request_iid
        )
    elif config.vcs_type == "github":
        return GitHubProvider(
            token=config.github_token,
            repository=config.github_repository,
            event_path=config.github_event_path
        )
    else:
        raise ValueError(f"Unsupported VCS provider: {config.vcs_type}")
