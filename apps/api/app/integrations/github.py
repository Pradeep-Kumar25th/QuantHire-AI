"""GitHub API connector stub for developer candidate sourcing."""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GitHubConnector:
    """
    GitHub API connector for sourcing developer candidates.
    
    NOTE: This is a STUB implementation. To activate:
    1. Create GitHub App or OAuth App: https://github.com/settings/apps
    2. Obtain client_id, client_secret, and personal access token
    3. Set environment variables:
       - GITHUB_CLIENT_ID
       - GITHUB_CLIENT_SECRET
       - GITHUB_PERSONAL_ACCESS_TOKEN (for search without user auth)
    4. Implement OAuth flow for user connections
    5. Replace stub methods with actual API calls
    
    API Documentation: https://docs.github.com/en/rest
    """
    
    API_BASE = "https://api.github.com"
    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        personal_access_token: Optional[str] = None,
    ):
        """
        Initialize GitHub connector.
        
        Args:
            client_id: GitHub app client ID
            client_secret: GitHub app client secret
            personal_access_token: PAT for authenticated requests
        """
        self.client_id = client_id or os.getenv("GITHUB_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GITHUB_CLIENT_SECRET")
        self.personal_access_token = personal_access_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        
        if not self.personal_access_token:
            logger.warning(
                "GitHub token not configured. "
                "Set GITHUB_PERSONAL_ACCESS_TOKEN to enable."
            )
            self.enabled = False
        else:
            self.enabled = True
            logger.info("GitHub connector initialized")
    
    async def search_users(
        self,
        query: str,
        location: Optional[str] = None,
        language: Optional[str] = None,
        min_followers: Optional[int] = None,
        limit: int = 30,
    ) -> List[Dict]:
        """
        Search GitHub users (potential candidates).
        
        NOTE: STUB IMPLEMENTATION
        
        Args:
            query: Search query (e.g., "python machine-learning")
            location: Geographic location
            language: Programming language
            min_followers: Minimum followers filter
            limit: Maximum results
            
        Returns:
            List of GitHub user profiles
        """
        logger.warning("STUB: GitHub user search not implemented")
        
        # Return mock data
        return [
            {
                "github_id": "stub_user_1",
                "username": "mock_developer",
                "name": "Mock GitHub Developer",
                "bio": "Python developer interested in ML",
                "location": location or "Qatar",
                "public_repos": 45,
                "followers": 120,
                "languages": [language] if language else ["Python", "JavaScript"],
                "profile_url": "https://github.com/mock_developer",
                "avatar_url": "https://avatars.githubusercontent.com/u/1234567",
                "note": "STUB: Configure GitHub API to fetch real profiles"
            }
        ]
    
    async def get_user_profile(self, username: str) -> Dict:
        """
        Get detailed GitHub user profile.
        
        NOTE: STUB IMPLEMENTATION
        
        Args:
            username: GitHub username
            
        Returns:
            User profile with repositories and contributions
        """
        logger.warning("STUB: GitHub profile fetch not implemented")
        
        return {
            "username": username,
            "name": "Mock User",
            "bio": "Software Engineer",
            "note": "Configure GitHub API to fetch real data"
        }
    
    async def get_user_repositories(
        self,
        username: str,
        sort: str = "updated",
        limit: int = 10,
    ) -> List[Dict]:
        """
        Get user's public repositories.
        
        NOTE: STUB IMPLEMENTATION
        
        Args:
            username: GitHub username
            sort: Sort order (updated, stars, forks)
            limit: Maximum repos to return
            
        Returns:
            List of repositories with stats
        """
        logger.warning("STUB: GitHub repositories fetch not implemented")
        
        return [
            {
                "name": "ml-platform",
                "description": "Machine learning serving platform",
                "language": "Python",
                "stars": 125,
                "forks": 23,
                "updated_at": "2024-10-01T10:00:00Z",
                "topics": ["machine-learning", "python", "fastapi"],
                "note": "STUB: Real API returns actual repository data"
            }
        ]
    
    async def analyze_user_activity(self, username: str) -> Dict:
        """
        Analyze user's GitHub activity and contributions.
        
        NOTE: STUB IMPLEMENTATION
        
        Returns contribution stats, languages, and activity patterns.
        """
        logger.warning("STUB: GitHub activity analysis not implemented")
        
        return {
            "username": username,
            "total_contributions_last_year": 847,
            "top_languages": ["Python", "TypeScript", "Go"],
            "activity_pattern": "Very active",
            "note": "STUB: Real implementation analyzes commit history"
        }


# Setup instructions
SETUP_INSTRUCTIONS = """
GitHub Integration Setup
========================

1. Create GitHub App or OAuth App:
   - GitHub App (recommended): https://github.com/settings/apps
   - OAuth App (simpler): https://github.com/settings/developers
   - Note client_id and client_secret

2. Generate Personal Access Token (for API access):
   - Go to: https://github.com/settings/tokens
   - Generate new token (classic)
   - Select scopes: read:user, user:email, read:org
   - Save token securely

3. Set Environment Variables:
   export GITHUB_CLIENT_ID="your_client_id"
   export GITHUB_CLIENT_SECRET="your_client_secret"
   export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token"

4. Configure OAuth Callback:
   - Set callback URL: http://localhost:3000/api/integrations/github/callback
   - Update in GitHub app settings

5. Implement Real API Calls:
   - Replace stub methods in apps/api/app/integrations/github.py
   - Add proper error handling
   - Implement rate limit handling (5000 req/hour authenticated)
   - Add caching to reduce API calls

6. Test Integration:
   - Test OAuth flow
   - Test user search
   - Test profile fetching
   - Test repository analysis

API Documentation:
- REST API: https://docs.github.com/en/rest
- GraphQL API: https://docs.github.com/en/graphql
- Rate Limits: https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting

Example Usage:
-------------
from app.integrations.github import GitHubConnector

connector = GitHubConnector()
users = await connector.search_users(
    query="python machine-learning location:qatar",
    min_followers=50,
    limit=30
)
"""


def print_setup_instructions():
    """Print GitHub setup instructions."""
    print(SETUP_INSTRUCTIONS)












