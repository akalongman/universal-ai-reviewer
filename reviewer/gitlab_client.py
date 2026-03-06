import gitlab

class GitLabClient:
    def __init__(self, url, token, project_id, mr_iid):
        self.gl = gitlab.Gitlab(url=url, private_token=token)
        self.project = self.gl.projects.get(project_id)
        self.mr = self.project.mergerequests.get(mr_iid)

    def get_mr_details(self):
        return {
            "title": self.mr.title,
            "description": self.mr.description or "No description provided."
        }

    def create_placeholder_comment(self, provider_name):
        body = f"⏳ **{provider_name.capitalize()} is reviewing your code...**\n*(This usually takes 10-20 seconds)*"
        return self.mr.notes.create({'body': body})

    def update_or_create_comment(self, note, review_text, provider_name):
        final_body = f"### 🤖 AI Code Review ({provider_name.capitalize()})\n\n{review_text}"
        if note:
            note.body = final_body
            note.save()
        else:
            self.mr.notes.create({'body': final_body})
