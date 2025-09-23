from django.contrib import admin
from .models import GitHubProfile, GitHubRepository, GitHubIssue, SyncLog, GitHubIssueComment

@admin.register(GitHubProfile)
class GitHubProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'github_username', 'last_sync', 'created_at')
    search_fields = ('user__username', 'github_username')
    raw_id_fields = ('user',)

@admin.register(GitHubRepository)
class GitHubRepositoryAdmin(admin.ModelAdmin):
    list_display = ('project', 'repository_owner', 'repository_name', 'is_private', 'last_synced')
    search_fields = ('project__name', 'repository_owner', 'repository_name')
    raw_id_fields = ('project',)

@admin.register(GitHubIssue)
class GitHubIssueAdmin(admin.ModelAdmin):
    list_display = ('repository', 'issue_number', 'issue_title', 'status', 'task', 'last_synced')
    list_filter = ('status', 'repository')
    search_fields = ('issue_title', 'issue_body', 'repository__repository_name')
    raw_id_fields = ('repository', 'task')

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'repository', 'action', 'status', 'created_at')
    list_filter = ('action', 'status')
    search_fields = ('message', 'user__username')
    raw_id_fields = ('user', 'repository')

@admin.register(GitHubIssueComment)
class GitHubIssueCommentAdmin(admin.ModelAdmin):
    list_display = ('github_issue', 'comment_id', 'user_login', 'github_created_at', 'last_synced')
    list_filter = ('github_issue__repository',)
    search_fields = ('body', 'user_login', 'github_issue__issue_title')
    raw_id_fields = ('github_issue', 'system_message')
