import git
from github import Github
import pandas as pd
from datetime import datetime, timezone

from decouple import config

gh = Github(config('GITHUB_ACCESS_TOKEN'))
repo_name = "apache/lucene"
repo = gh.get_repo(repo_name)

def has_replicated_code(pr_files):
    file_names = [file.filename for file in pr_files]
    return len(file_names) != len(set(file_names))

def check_pr_comments(pr):
    comments = pr.get_issue_comments()
    wont_fix_keywords = ["won't fix", "wontfix", "will not fix", "not addressing", "Won't Do"]
    superseded_keywords = ["superseded", "replaced by", "duplicate of", "superseding"]

    wont_fix = False
    superseded = False

    for comment in comments:
        comment_body = comment.body.lower()
        if any(keyword in comment_body for keyword in wont_fix_keywords):
            wont_fix = True
        if any(keyword in comment_body for keyword in superseded_keywords):
            superseded = True

    return wont_fix, superseded


def check_pr_labels(pr):
    """Function to check PR labels for specific tags
    """
    wont_fix_tags = ["wontfix", "invalid", "not fixable"]
    superseded_tags = ["duplicate", "superseded"]

    wont_fix = any(label.name.lower() in wont_fix_tags for label in pr.labels)
    superseded = any(label.name.lower() in superseded_tags for label in pr.labels)

    return wont_fix, superseded


def check_ci_status(pr):
    pr_commits = pr.get_commits()
    latest_commit = pr_commits.reversed[0]
    status = latest_commit.get_combined_status()

    if status.state == 'success':
        return 'success'
    elif status.state == 'failure':
        return 'failure'
    else:
        return 'pending'

def collect_pr_metrics(repo):
    pr_data = []
    counter = 0

    for pr in repo.get_pulls(state='all'):
        if counter == 500:
            break
        try:
            print(f'Scraping PR ({counter}/500), Current Progress {counter*100/500:.2f}%')
            created_at = pr.created_at.replace(tzinfo=timezone.utc)
            closed_at = pr.closed_at.replace(tzinfo=timezone.utc) if pr.closed_at else datetime.now(timezone.utc)
            time_to_review = (closed_at - created_at).total_seconds() / 3600

            comments = pr.comments
            review_comments = pr.review_comments
            changed_files = pr.changed_files
            additions = pr.additions
            deletions = pr.deletions
            total_changes = additions + deletions
            is_merged = pr.is_merged()
            user_type = 'first_timer' if pr.user.contributions == 1 else 'regular'

            ci_status = check_ci_status(pr)

            pr_files = list(pr.get_files())
            replicated_code = has_replicated_code(pr_files)

            wont_fix_comments, superseded_comments = check_pr_comments(pr)
            wont_fix_labels, superseded_labels = check_pr_labels(pr)
            wont_fix = wont_fix_comments or wont_fix_labels
            superseded = superseded_comments or superseded_labels

            pr_data.append([
                pr.number, time_to_review, comments, review_comments,
                changed_files, additions, deletions, total_changes,
                is_merged, user_type, ci_status, replicated_code, wont_fix, superseded
            ])
            counter += 1
        except Exception as e:
            print(f'Error: {e}')
            continue

    columns = [
        'PR_Number', 'Time_to_Review', 'Comments', 'Review_Comments',
        'Changed_Files', 'Additions', 'Deletions', 'Total_Changes',
        'Is_Merged', 'User_Type', 'CI_Status', 'Replicated_Code', 'Wont_Fix', 'Superseded'
    ]

    pr_df = pd.DataFrame(pr_data, columns=columns)
    return pr_df

pr_dfs = collect_pr_metrics(repo)
pr_dfs.to_csv('pr_metrics.csv', index=False)
