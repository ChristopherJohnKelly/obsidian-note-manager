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
    
    # Try both token formats (classic PAT uses "token", fine-grained might need "Bearer")
    headers_token = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    headers_bearer = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Try with "token" format first (for classic PATs)
        response = requests.post(api_url, headers=headers_token, timeout=10)
        
        # If 403 with token format, try Bearer format (for fine-grained PATs)
        if response.status_code == 403:
            response = requests.post(api_url, headers=headers_bearer, timeout=10)
        
        # Get response details for error messages
        response_text = response.text
        try:
            response_json = response.json()
            error_message = response_json.get("message", "")
        except:
            error_message = response_text[:200] if response_text else ""
        
        response.raise_for_status()
        
        token_data = response.json()
        registration_token = token_data.get("token")
        
        if not registration_token:
            raise ValueError("Registration token not found in API response")
        
        return registration_token
        
    except requests.exceptions.HTTPError as e:
        response = e.response
        status_code = response.status_code if response else None
        try:
            error_json = response.json() if response else {}
            error_message = error_json.get("message", response.text[:200] if response else "Unknown error")
        except:
            error_message = response.text[:200] if response else "Unknown error"
        
        if status_code == 401:
            raise requests.HTTPError(f"Authentication failed: Invalid PAT or insufficient permissions. "
                                    f"Ensure PAT has 'repo' scope or fine-grained 'Actions: Read and write' permission. "
                                    f"Error: {error_message} Status: {status_code}", response=response)
        elif status_code == 404:
            raise requests.HTTPError(f"Repository not found or no access: {owner}/{repo_name}. "
                                    f"Check repository URL and PAT permissions. "
                                    f"Error: {error_message} Status: {status_code}", 
                                    response=response)
        elif status_code == 403:
            raise requests.HTTPError(f"Forbidden: PAT may not have required permissions or fine-grained token not installed. "
                                    f"Fine-grained tokens must be installed/authorized for the repository. "
                                    f"Error: {error_message} Status: {status_code}. "
                                    f"Verify the token is installed for {owner}/{repo_name} at: "
                                    f"https://github.com/settings/tokens?type=beta", 
                                    response=response)
        else:
            raise requests.HTTPError(f"GitHub API error: {status_code} - {error_message}", 
                                    response=response)
    except requests.exceptions.RequestException as e:
        # Handle all request exceptions with detailed error info
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_json = e.response.json()
                error_message = error_json.get("message", e.response.text[:200])
            except:
                error_message = e.response.text[:200] if e.response.text else str(e)
            status_code = e.response.status_code
            raise Exception(f"GitHub API error: {status_code} - {error_message}. Full error: {error_msg}")
        else:
            raise Exception(f"Network error while fetching registration token: {error_msg}")
    except Exception as e:
        # Catch any other unexpected exceptions
        raise Exception(f"Unexpected error while fetching registration token: {type(e).__name__}: {str(e)}")


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
    except requests.HTTPError as e:
        # HTTPError from requests library
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_json = e.response.json()
                api_message = error_json.get("message", "")
            except:
                api_message = e.response.text[:200] if e.response.text else ""
            status_code = e.response.status_code
            print(f"Error: {error_msg}", file=sys.stderr)
            if api_message:
                print(f"GitHub API message: {api_message}", file=sys.stderr)
            print(f"Status code: {status_code}", file=sys.stderr)
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Generic exception handler with full error details
        import traceback
        print(f"Error: {type(e).__name__}: {str(e)}", file=sys.stderr)
        print(f"Traceback: {traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
