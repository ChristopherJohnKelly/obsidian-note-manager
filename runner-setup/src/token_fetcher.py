import sys
import os
import requests
from urllib.parse import urlparse


def get_registration_token(repo_url: str, pat: str) -> str:
    """
    Fetches a registration token for a GitHub Actions self-hosted runner using a PAT.
    
    Args:
        repo_url: Full GitHub repository URL (e.g., "https://github.com/owner/repo")
        pat: Personal Access Token with repo scope (or fine-grained Actions permission)
        
    Returns:
        str: Registration token (valid for ~1 hour)
        
    Raises:
        ValueError: If repo_url format is invalid
        requests.HTTPError: If API request fails (401, 404, etc.)
        Exception: For other errors (network issues, etc.)
    """
    # Parse repository owner and name from URL
    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip('/').split('/')
    
    if len(path_parts) < 2:
        raise ValueError(f"Invalid repository URL format: {repo_url}. Expected format: https://github.com/owner/repo")
    
    owner = path_parts[0]
    repo_name = path_parts[1]
    
    # GitHub API endpoint for registration tokens
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runners/registration-token"
    
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.post(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        registration_token = token_data.get("token")
        
        if not registration_token:
            raise ValueError("Registration token not found in API response")
        
        return registration_token
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise requests.HTTPError(f"Authentication failed: Invalid PAT or insufficient permissions. "
                                    f"Ensure PAT has 'repo' scope or fine-grained 'Actions: Read and write' permission. "
                                    f"Status: {e.response.status_code}", response=e.response)
        elif e.response.status_code == 404:
            raise requests.HTTPError(f"Repository not found or no access: {owner}/{repo_name}. "
                                    f"Check repository URL and PAT permissions. Status: {e.response.status_code}", 
                                    response=e.response)
        elif e.response.status_code == 403:
            raise requests.HTTPError(f"Forbidden: PAT may not have required permissions. "
                                    f"Status: {e.response.status_code}", response=e.response)
        else:
            raise requests.HTTPError(f"GitHub API error: {e.response.status_code} - {e.response.text}", 
                                    response=e.response)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error while fetching registration token: {e}")


def main():
    """CLI entry point for token fetcher."""
    if len(sys.argv) < 3:
        print("Usage: python3 token_fetcher.py <repo_url> <pat>", file=sys.stderr)
        sys.exit(1)
    
    repo_url = sys.argv[1]
    pat = sys.argv[2]
    
    try:
        token = get_registration_token(repo_url, pat)
        print(token)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
