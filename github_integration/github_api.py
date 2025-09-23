import requests
import json
import logging
import random
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class GitHubAPI:
    """
    GitHub API ile iletişim kurmak için kullanılan yardımcı sınıf.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, access_token=None, github_profile=None):
        """
        GitHub API ile iletişim kurmak için token bilgilerini alır.
        Doğrudan token veya GitHubProfile objesi verilebilir.
        """
        # Global demo mod veya kişisel demo mod kontrolü
        self.demo_mode = getattr(settings, 'GITHUB_DEMO_MODE', False)
        
        # GitHub profili veya token kontrolü
        if github_profile:
            self.access_token = github_profile.access_token
            self.github_profile = github_profile
            self.github_username = github_profile.github_username
        else:
            self.access_token = access_token
            self.github_profile = None
            self.github_username = None
        
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {self.access_token}' if self.access_token else '',
        }
        
        # API sınırı, hız limiti ve hata sayacı
        self.rate_limit = None
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        self.error_count = 0
        self.max_errors = 5  # Arka arkaya maksimum hata sayısı
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """
        GitHub API'sine istek yapar.
        
        Parametreler:
            method (str): HTTP metodu ('get', 'post', 'put', 'delete', vs.)
            endpoint (str): API endpoint'i ('/user', '/repos/{owner}/{repo}', vs.)
            data (dict): İstek gövdesi
            params (dict): İstek parametreleri
            
        Dönüş:
            dict or list: API yanıtı (JSON parse edilmiş)
        """
        # Demo modda ise, sahte veri döndür
        if self.demo_mode:
            return self._get_demo_data(method, endpoint, data, params)
        
        # Token veya profil kontrolü - eksikse None döndür
        if not self.access_token:
            logger.error("GitHub API request failed: No access token provided")
            return None
        
        # Token süresi dolmuşsa yenilemeyi dene (profil varsa)
        if self.github_profile and hasattr(self.github_profile, 'token_expires_at') and self.github_profile.token_expires_at:
            if timezone.now() > self.github_profile.token_expires_at:
                if self._refresh_token():
                    # Token yenileme başarılı, headers güncelle
                    self.headers['Authorization'] = f'token {self.access_token}'
                else:
                    # Token yenilenemedi, None döndür
                    logger.error("GitHub API request failed: Token expired and refresh failed")
                    return None
        
        # Endpoint'in başında / olduğundan emin ol
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            # İstek yap
            if method.lower() == 'get':
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method.lower() == 'post':
                response = requests.post(url, headers=self.headers, json=data, params=params, timeout=10)
            elif method.lower() == 'put':
                response = requests.put(url, headers=self.headers, json=data, params=params, timeout=10)
            elif method.lower() == 'patch':
                response = requests.patch(url, headers=self.headers, json=data, params=params, timeout=10)
            elif method.lower() == 'delete':
                response = requests.delete(url, headers=self.headers, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Hız limitini güncelle
            self._update_rate_limit_info(response.headers)
            
            # HTTP hata kodları
            if response.status_code >= 400:
                # 401 Unauthorized - Kimlik doğrulama hatası, token geçersiz
                if response.status_code == 401:
                    # Token'ı geçersiz olarak işaretle (profil varsa)
                    if self.github_profile and hasattr(self.github_profile, 'token_expires_at'):
                        self.github_profile.token_expires_at = timezone.now() - timedelta(seconds=1)
                        self.github_profile.save()
                    
                    logger.error(f"GitHub API 401 Unauthorized: Token may be invalid or expired")
                    return None
                    
                # 403 Forbidden - Hız limiti aşıldı veya kaynak erişimi engellendi
                elif response.status_code == 403:
                    if 'X-RateLimit-Remaining' in response.headers and int(response.headers.get('X-RateLimit-Remaining', 1)) == 0:
                        reset_time = datetime.fromtimestamp(int(response.headers.get('X-RateLimit-Reset', 0)))
                        logger.error(f"GitHub API rate limit exceeded. Reset at {reset_time}")
                    else:
                        logger.error(f"GitHub API access forbidden: {response.text}")
                    return None
                    
                # 404 Not Found - Endpoint veya istenen kaynak bulunamadı
                elif response.status_code == 404:
                    logger.warning(f"GitHub API resource not found: {url}")
                    return None
                    
                # Diğer HTTP hataları
                else:
                    logger.error(f"GitHub API error: HTTP {response.status_code} - {response.text}")
                    return None
            
            # Başarılı yanıt
            if response.status_code in (200, 201, 202, 204):
                self.error_count = 0  # Hata sayacını sıfırla
                
                # No content veya boş veri durumu
                if response.status_code == 204 or not response.text.strip():
                    return {}
                
                # JSON parse et
                try:
                    return response.json()
                except ValueError:
                    logger.error(f"Invalid JSON response from GitHub API: {response.text[:100]}...")
                    return None
            
            # Beklenmeyen durum
            logger.warning(f"Unexpected HTTP status from GitHub API: {response.status_code}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"GitHub API request timeout: {url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"GitHub API connection error: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in GitHub API request: {str(e)}")
            return None
    
    def _update_rate_limit_info(self, headers):
        """
        API yanıt başlıklarından rate limit bilgilerini günceller.
        """
        if 'X-RateLimit-Limit' in headers:
            self.rate_limit = int(headers['X-RateLimit-Limit'])
        
        if 'X-RateLimit-Remaining' in headers:
            self.rate_limit_remaining = int(headers['X-RateLimit-Remaining'])
            # Rate limit yakında dolacak, uyarı logla
            if self.rate_limit_remaining < 10:
                logger.warning(f"GitHub API rate limit almost reached. Remaining: {self.rate_limit_remaining}")
        
        if 'X-RateLimit-Reset' in headers:
            reset_time = int(headers['X-RateLimit-Reset'])
            self.rate_limit_reset = datetime.fromtimestamp(reset_time)
    
    def _refresh_token(self):
        """
        GitHub access token'ı yenilemeyi dener.
        Başarılı olursa True, başarısız olursa False döndürür.
        """
        # Profil yoksa veya refresh token yoksa yenileme yapılamaz
        if not self.github_profile or not self.github_profile.refresh_token:
            return False
        
        try:
            # Kişisel OAuth mı sistem OAuth mı kontrol et
            if self.github_profile.use_personal_oauth and self.github_profile.client_id and self.github_profile.client_secret:
                client_id = self.github_profile.client_id
                client_secret = self.github_profile.client_secret
            else:
                client_id = settings.GITHUB_CLIENT_ID
                client_secret = settings.GITHUB_CLIENT_SECRET
            
            # Token yenileme isteği
            token_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': self.github_profile.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(
                'https://github.com/login/oauth/access_token',
                data=token_data,
                headers={'Accept': 'application/json'},
                timeout=10
            )
            
            response.raise_for_status()
            token_info = response.json()
            
            if 'access_token' in token_info:
                # Token güncelleme başarılı
                self.access_token = token_info['access_token']
                self.headers['Authorization'] = f'token {self.access_token}'
                
                # Profili güncelle
                self.github_profile.access_token = token_info['access_token']
                
                # Refresh token varsa güncelle
                if 'refresh_token' in token_info:
                    self.github_profile.refresh_token = token_info['refresh_token']
                
                # Token süresi bilgisi
                if 'expires_in' in token_info:
                    expires_in = token_info.get('expires_in', 28800)  # default: 8 saat
                    self.github_profile.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
                
                self.github_profile.save()
                logger.info(f"GitHub token successfully refreshed for user: {self.github_profile.user.username}")
                return True
            else:
                logger.error(f"GitHub token refresh failed: {token_info}")
                return False
        
        except Exception as e:
            logger.error(f"GitHub token refresh error: {str(e)}")
            return False
    
    def _paginate_request(self, endpoint, params=None, max_items=None):
        """
        Sayfalama ile GitHub API'den veri alır.
        """
        if params is None:
            params = {}
        
        params['per_page'] = 100  # Her sayfada maksimum öğe
        
        results = []
        page = 1
        
        while True:
            params['page'] = page
            page_results = self._make_request('get', endpoint, params=params)
            
            if not page_results or not isinstance(page_results, list) or len(page_results) == 0:
                break
            
            results.extend(page_results)
            
            # Öğe sayısı sınırlandırılmışsa ve sınıra ulaşıldıysa döngüyü sonlandır
            if max_items and len(results) >= max_items:
                results = results[:max_items]
                break
            
            page += 1
        
        return results
    
    def _get_demo_data(self, method, endpoint, data=None, params=None):
        """
        Demo modu için sahte veri üretir.
        """
        # Endpoints için sahte veriler
        if endpoint == '/user' or endpoint.startswith('/user/'):
            if endpoint == '/user':
                # Kullanıcı bilgileri
                return {
                    'login': 'demo-user',
                    'id': 12345,
                    'avatar_url': 'https://avatars.githubusercontent.com/u/12345?v=4',
                    'html_url': 'https://github.com/demo-user',
                    'name': 'Demo User',
                    'company': 'Demo Company',
                    'blog': 'https://demo-user.github.io',
                    'location': 'Demo City',
                    'email': 'demo@example.com',
                    'bio': 'This is a demo user profile for testing purposes.',
                    'public_repos': 10,
                    'followers': 25,
                    'following': 30,
                    'created_at': '2015-01-01T00:00:00Z',
                    'updated_at': '2023-01-01T00:00:00Z'
                }
            elif endpoint == '/user/repos':
                # Kullanıcının repository'leri
                return self._get_demo_repositories(params)

        elif endpoint.startswith('/repos/'):
            parts = endpoint.split('/')
            if len(parts) >= 4:
                owner = parts[2]
                repo = parts[3]
                
                if len(parts) == 4:
                    # Tekil repository bilgisi
                    return self._get_demo_repository(owner, repo)
                elif len(parts) >= 5:
                    if parts[4] == 'issues':
                        if len(parts) == 5:
                            # Repository'deki issue'lar
                            return self._get_demo_issues(owner, repo, params)
                        elif len(parts) == 6 and parts[5].isdigit():
                            # Tekil issue bilgisi
                            return self._get_demo_issue(owner, repo, int(parts[5]))
                        elif len(parts) >= 7 and parts[5].isdigit() and parts[6] == 'comments':
                            # Issue yorumları
                            return self._get_demo_issue_comments(owner, repo, int(parts[5]), params)
                    elif parts[4] == 'pulls':
                        # Pull request'ler
                        return self._get_demo_pull_requests(owner, repo, params)
                    elif parts[4] == 'hooks':
                        # Webhook'lar
                        return self._get_demo_hooks(owner, repo)
                    
        # Bilinmeyen endpoint için boş liste döndür
        return []
    
    def _get_demo_repositories(self, params=None):
        """Demo repository listesi üretir"""
        repos = [
            {
                'id': 100001,
                'name': 'demo-project',
                'full_name': 'demo-user/demo-project',
                'owner': {'login': 'demo-user'},
                'html_url': 'https://github.com/demo-user/demo-project',
                'description': 'A demo project for testing',
                'fork': False,
                'created_at': '2022-01-01T00:00:00Z',
                'updated_at': '2023-06-15T00:00:00Z',
                'pushed_at': '2023-06-10T00:00:00Z',
                'language': 'Python',
                'has_issues': True,
                'has_wiki': True,
                'default_branch': 'main',
                'open_issues_count': 5,
                'stargazers_count': 25,
                'watchers_count': 25,
                'forks_count': 10,
                'private': False
            },
            {
                'id': 100002,
                'name': 'demo-webapp',
                'full_name': 'demo-user/demo-webapp',
                'owner': {'login': 'demo-user'},
                'html_url': 'https://github.com/demo-user/demo-webapp',
                'description': 'A demo web application',
                'fork': False,
                'created_at': '2022-02-15T00:00:00Z',
                'updated_at': '2023-07-20T00:00:00Z',
                'pushed_at': '2023-07-15T00:00:00Z',
                'language': 'JavaScript',
                'has_issues': True,
                'has_wiki': True,
                'default_branch': 'main',
                'open_issues_count': 8,
                'stargazers_count': 40,
                'watchers_count': 40,
                'forks_count': 15,
                'private': False
            },
            {
                'id': 100003,
                'name': 'forked-library',
                'full_name': 'demo-user/forked-library',
                'owner': {'login': 'demo-user'},
                'html_url': 'https://github.com/demo-user/forked-library',
                'description': 'A forked library',
                'fork': True,
                'created_at': '2022-03-20T00:00:00Z',
                'updated_at': '2023-05-10T00:00:00Z',
                'pushed_at': '2023-05-05T00:00:00Z',
                'language': 'Java',
                'has_issues': False,
                'has_wiki': True,
                'default_branch': 'master',
                'open_issues_count': 0,
                'stargazers_count': 5,
                'watchers_count': 5,
                'forks_count': 2,
                'private': False
            }
        ]
        
        # Parametrelere göre filtreleme
        if params and 'visibility' in params and params['visibility'] != 'all':
            is_private = params['visibility'] == 'private'
            repos = [repo for repo in repos if repo['private'] == is_private]
        
        # Parametrelere göre sıralama
        if params and 'sort' in params:
            sort_key = params['sort']
            direction = -1 if params.get('direction') == 'desc' else 1
            
            if sort_key == 'updated':
                repos.sort(key=lambda x: x['updated_at'], reverse=(direction == -1))
            elif sort_key == 'created':
                repos.sort(key=lambda x: x['created_at'], reverse=(direction == -1))
            elif sort_key == 'stars':
                repos.sort(key=lambda x: x['stargazers_count'], reverse=(direction == -1))
        
        return repos
    
    def _get_demo_repository(self, owner, repo):
        """Demo tekil repository bilgisi üretir"""
        for repository in self._get_demo_repositories():
            if repository['owner']['login'] == owner and repository['name'] == repo:
                return repository
        
        # Belirtilen repository bulunamadı, yeni bir repository oluştur
        return {
            'id': 100000 + random.randint(1, 999),
            'name': repo,
            'full_name': f"{owner}/{repo}",
            'owner': {'login': owner},
            'html_url': f"https://github.com/{owner}/{repo}",
            'description': f"Demo repository for {owner}/{repo}",
            'fork': False,
            'created_at': '2022-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z',
            'pushed_at': '2023-01-01T00:00:00Z',
            'language': random.choice(['Python', 'JavaScript', 'Java', 'C#', 'Ruby']),
            'has_issues': True,
            'has_wiki': True,
            'default_branch': 'main',
            'open_issues_count': random.randint(0, 20),
            'stargazers_count': random.randint(0, 100),
            'watchers_count': random.randint(0, 100),
            'forks_count': random.randint(0, 50),
            'private': False
        }
    
    def _get_demo_issues(self, owner, repo, params=None):
        """Demo issue listesi üretir"""
        state = params.get('state', 'open') if params else 'open'
        
        issues = [
            {
                'id': 200001,
                'number': 1,
                'title': 'Demo Issue 1: Implement login functionality',
                'body': 'We need to implement secure login functionality with OAuth support.',
                'state': 'open',
                'created_at': '2023-01-10T00:00:00Z',
                'updated_at': '2023-01-15T00:00:00Z',
                'html_url': f"https://github.com/{owner}/{repo}/issues/1",
                'user': {'login': 'demo-contributor1'},
                'labels': [{'name': 'enhancement'}, {'name': 'frontend'}],
                'assignees': [{'login': 'demo-user'}]
            },
            {
                'id': 200002,
                'number': 2,
                'title': 'Demo Issue 2: Fix CSS responsive design',
                'body': 'The app is not displaying correctly on mobile devices.',
                'state': 'open',
                'created_at': '2023-02-05T00:00:00Z',
                'updated_at': '2023-02-10T00:00:00Z',
                'html_url': f"https://github.com/{owner}/{repo}/issues/2",
                'user': {'login': 'demo-user'},
                'labels': [{'name': 'bug'}, {'name': 'frontend'}],
                'assignees': [{'login': 'demo-contributor2'}]
            },
            {
                'id': 200003,
                'number': 3,
                'title': 'Demo Issue 3: Database optimization',
                'body': 'Database queries are slow, need to optimize indexes.',
                'state': 'closed',
                'created_at': '2023-01-20T00:00:00Z',
                'updated_at': '2023-03-01T00:00:00Z',
                'closed_at': '2023-03-01T00:00:00Z',
                'html_url': f"https://github.com/{owner}/{repo}/issues/3",
                'user': {'login': 'demo-contributor2'},
                'labels': [{'name': 'enhancement'}, {'name': 'backend'}],
                'assignees': [{'login': 'demo-user'}]
            }
        ]
        
        # Parametrelere göre filtreleme
        if state != 'all':
            issues = [issue for issue in issues if issue['state'] == state]
        
        return issues
    
    def _get_demo_issue(self, owner, repo, issue_number):
        """Demo tekil issue bilgisi üretir"""
        for issue in self._get_demo_issues(owner, repo):
            if issue['number'] == issue_number:
                return issue
        
        return None
    
    def _get_demo_issue_comments(self, owner, repo, issue_number, params=None):
        """Demo issue yorumları üretir"""
        comments = [
            {
                'id': 500001,
                'body': 'This is a very critical issue. We should prioritize this for the next sprint.',
                'user': {'login': 'demo-contributor1', 'avatar_url': 'https://avatars.githubusercontent.com/u/1'},
                'created_at': '2023-01-11T10:00:00Z',
                'updated_at': '2023-01-11T10:00:00Z',
                'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500001'
            },
            {
                'id': 500002,
                'body': 'I agree, this is affecting multiple users. Any ideas on how to fix this?',
                'user': {'login': 'demo-user', 'avatar_url': 'https://avatars.githubusercontent.com/u/2'},
                'created_at': '2023-01-12T09:00:00Z',
                'updated_at': '2023-01-12T09:00:00Z',
                'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500002'
            },
            {
                'id': 500003,
                'body': 'I think we should refactor the authentication module. The current implementation has several security issues.',
                'user': {'login': 'demo-contributor2', 'avatar_url': 'https://avatars.githubusercontent.com/u/3'},
                'created_at': '2023-01-13T14:00:00Z',
                'updated_at': '2023-01-13T14:00:00Z',
                'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500003'
            }
        ]
        
        # Issue numarasına göre farklı yorumlar göster
        if issue_number == 2:
            comments = [
                {
                    'id': 500004,
                    'body': 'This responsive design issue is causing problems on both iOS and Android devices.',
                    'user': {'login': 'demo-contributor2', 'avatar_url': 'https://avatars.githubusercontent.com/u/3'},
                    'created_at': '2023-02-06T11:00:00Z',
                    'updated_at': '2023-02-06T11:00:00Z',
                    'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500004'
                },
                {
                    'id': 500005,
                    'body': 'We need to implement a completely responsive layout using CSS Grid and Flexbox.',
                    'user': {'login': 'demo-user', 'avatar_url': 'https://avatars.githubusercontent.com/u/2'},
                    'created_at': '2023-02-07T15:30:00Z',
                    'updated_at': '2023-02-07T15:30:00Z',
                    'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500005'
                }
            ]
        elif issue_number == 3:
            comments = [
                {
                    'id': 500006,
                    'body': 'I have optimized the database queries by adding proper indexes.',
                    'user': {'login': 'demo-contributor2', 'avatar_url': 'https://avatars.githubusercontent.com/u/3'},
                    'created_at': '2023-02-10T09:45:00Z',
                    'updated_at': '2023-02-10T09:45:00Z',
                    'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500006'
                },
                {
                    'id': 500007,
                    'body': 'Great job! The performance improvements are significant. Closing this issue.',
                    'user': {'login': 'demo-user', 'avatar_url': 'https://avatars.githubusercontent.com/u/2'},
                    'created_at': '2023-03-01T11:20:00Z',
                    'updated_at': '2023-03-01T11:20:00Z',
                    'html_url': f'https://github.com/{owner}/{repo}/issues/{issue_number}#issuecomment-500007'
                }
            ]
        
        return comments
    
    def _get_demo_pull_requests(self, owner, repo, params=None):
        """Demo pull request listesi üretir"""
        state = params.get('state', 'open') if params else 'open'
        
        prs = [
            {
                'id': 300001,
                'number': 10,
                'title': 'Demo PR: Add new login page',
                'body': 'This PR adds a new login page with improved UI/UX.',
                'state': 'open',
                'created_at': '2023-05-10T00:00:00Z',
                'updated_at': '2023-05-15T00:00:00Z',
                'html_url': f"https://github.com/{owner}/{repo}/pull/10",
                'user': {'login': 'demo-contributor1'},
                'head': {'ref': 'feature/login-page'},
                'base': {'ref': 'main'}
            },
            {
                'id': 300002,
                'number': 11,
                'title': 'Demo PR: Fix responsive design',
                'body': 'This PR fixes responsive design issues on mobile devices.',
                'state': 'open',
                'created_at': '2023-05-20T00:00:00Z',
                'updated_at': '2023-05-25T00:00:00Z',
                'html_url': f"https://github.com/{owner}/{repo}/pull/11",
                'user': {'login': 'demo-contributor2'},
                'head': {'ref': 'bugfix/responsive-design'},
                'base': {'ref': 'main'}
            },
            {
                'id': 300003,
                'number': 12,
                'title': 'Demo PR: Database optimizations',
                'body': 'This PR adds database indexes for performance optimization.',
                'state': 'closed',
                'created_at': '2023-04-10T00:00:00Z',
                'updated_at': '2023-04-20T00:00:00Z',
                'closed_at': '2023-04-20T00:00:00Z',
                'html_url': f"https://github.com/{owner}/{repo}/pull/12",
                'user': {'login': 'demo-user'},
                'head': {'ref': 'feature/db-optimization'},
                'base': {'ref': 'main'}
            }
        ]
        
        # Parametrelere göre filtreleme
        if state != 'all':
            prs = [pr for pr in prs if pr['state'] == state]
        
        return prs
    
    def _get_demo_hooks(self, owner, repo):
        """Demo webhook listesi üretir"""
        return [
            {
                'id': 400001,
                'name': 'web',
                'active': True,
                'events': ['push', 'pull_request', 'issues'],
                'config': {
                    'url': 'https://example.com/webhook',
                    'content_type': 'json',
                    'insecure_ssl': '0'
                },
                'created_at': '2023-01-15T00:00:00Z',
                'updated_at': '2023-01-15T00:00:00Z'
            }
        ]
    
    def get_user_info(self):
        """
        Kimliği doğrulanmış kullanıcının GitHub bilgilerini alır.
        """
        return self._make_request('get', '/user')
    
    def get_repositories(self, visibility='all', max_repos=None):
        """
        Kullanıcının erişimi olan repository'leri listeler.
        """
        params = {'visibility': visibility, 'sort': 'updated', 'direction': 'desc'}
        return self._paginate_request('/user/repos', params, max_items=max_repos)
    
    def get_repository(self, owner, repo):
        """
        Belirli bir repository hakkında detaylı bilgi alır.
        """
        return self._make_request('get', f'/repos/{owner}/{repo}')
    
    def create_repository(self, name, description=None, private=False, has_issues=True, has_wiki=True):
        """
        Yeni bir repository oluşturur.
        """
        data = {
            'name': name,
            'description': description,
            'private': private,
            'has_issues': has_issues,
            'has_wiki': has_wiki,
            'auto_init': True,  # README dosyası otomatik oluştur
        }
        return self._make_request('post', '/user/repos', data=data)
    
    def get_issues(self, owner, repo, state='all', max_issues=None):
        """
        Repository'deki issue'ları listeler.
        """
        params = {'state': state, 'sort': 'updated', 'direction': 'desc'}
        return self._paginate_request(f'/repos/{owner}/{repo}/issues', params, max_items=max_issues)
    
    def get_issue(self, owner, repo, issue_number):
        """
        Belirli bir issue hakkında detaylı bilgi alır.
        """
        return self._make_request('get', f'/repos/{owner}/{repo}/issues/{issue_number}')
    
    def create_issue(self, owner, repo, title, body=None, labels=None, assignees=None):
        """
        Repository'de yeni bir issue oluşturur.
        """
        data = {
            'title': title,
            'body': body,
        }
        
        if labels:
            data['labels'] = labels
        
        if assignees:
            data['assignees'] = assignees
        
        return self._make_request('post', f'/repos/{owner}/{repo}/issues', data=data)
    
    def update_issue(self, owner, repo, issue_number, title=None, body=None, state=None, labels=None, assignees=None):
        """
        Var olan bir issue'yu günceller.
        """
        data = {}
        
        if title:
            data['title'] = title
        
        if body:
            data['body'] = body
        
        if state:
            data['state'] = state
        
        if labels:
            data['labels'] = labels
        
        if assignees:
            data['assignees'] = assignees
        
        return self._make_request('patch', f'/repos/{owner}/{repo}/issues/{issue_number}', data=data)
    
    def close_issue(self, owner, repo, issue_number):
        """
        Bir issue'yu kapatır.
        """
        return self.update_issue(owner, repo, issue_number, state='closed')
    
    def reopen_issue(self, owner, repo, issue_number):
        """
        Kapalı bir issue'yu yeniden açar.
        """
        return self.update_issue(owner, repo, issue_number, state='open')
    
    def get_pull_requests(self, owner, repo, state='open', max_prs=None):
        """
        Repository'deki pull request'leri listeler.
        """
        params = {'state': state, 'sort': 'updated', 'direction': 'desc'}
        return self._paginate_request(f'/repos/{owner}/{repo}/pulls', params, max_items=max_prs)
    
    def get_pull_request(self, owner, repo, pr_number):
        """
        Belirli bir pull request hakkında detaylı bilgi alır.
        """
        return self._make_request('get', f'/repos/{owner}/{repo}/pulls/{pr_number}')
    
    def create_pull_request(self, owner, repo, title, head, base, body=None):
        """
        Repository'de yeni bir pull request oluşturur.
        
        Parametreler:
            owner (str): Repository'nin sahibi
            repo (str): Repository adı
            title (str): Pull request başlığı
            head (str): Değişikliklerin olduğu branch
            base (str): Değişikliklerin uygulanacağı hedef branch
            body (str, optional): Pull request açıklaması
        """
        data = {
            'title': title,
            'head': head,
            'base': base,
        }
        
        if body:
            data['body'] = body
        
        return self._make_request('post', f'/repos/{owner}/{repo}/pulls', data=data)
    
    def merge_pull_request(self, owner, repo, pr_number, commit_message=None):
        """
        Bir pull request'i birleştirir (merge).
        """
        data = {}
        
        if commit_message:
            data['commit_message'] = commit_message
        
        return self._make_request('put', f'/repos/{owner}/{repo}/pulls/{pr_number}/merge', data=data)
    
    def get_branches(self, owner, repo, max_branches=None):
        """
        Repository'deki branch'leri listeler.
        """
        return self._paginate_request(f'/repos/{owner}/{repo}/branches', max_items=max_branches)
    
    def get_commits(self, owner, repo, branch=None, max_commits=None):
        """
        Repository'deki commit'leri listeler.
        """
        params = {}
        if branch:
            params['sha'] = branch
        
        return self._paginate_request(f'/repos/{owner}/{repo}/commits', params, max_items=max_commits)
    
    def get_contents(self, owner, repo, path='', ref=None):
        """
        Repository'deki bir dosya veya dizinin içeriğini alır.
        """
        params = {}
        if ref:
            params['ref'] = ref
        
        return self._make_request('get', f'/repos/{owner}/{repo}/contents/{path}', params=params)
    
    def create_file(self, owner, repo, path, message, content, branch=None):
        """
        Repository'de yeni bir dosya oluşturur.
        
        Not: 'content' parametresi base64 kodlanmış olmalıdır.
        """
        import base64
        
        data = {
            'message': message,
            'content': base64.b64encode(content.encode('utf-8')).decode('utf-8')
        }
        
        if branch:
            data['branch'] = branch
        
        return self._make_request('put', f'/repos/{owner}/{repo}/contents/{path}', data=data)
    
    def update_file(self, owner, repo, path, message, content, sha, branch=None):
        """
        Repository'deki bir dosyayı günceller.
        
        Not: 'content' parametresi base64 kodlanmış olmalıdır ve dosyanın mevcut SHA değeri gereklidir.
        """
        import base64
        
        data = {
            'message': message,
            'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            'sha': sha
        }
        
        if branch:
            data['branch'] = branch
        
        return self._make_request('put', f'/repos/{owner}/{repo}/contents/{path}', data=data)
    
    def get_webhooks(self, owner, repo):
        """
        Repository'deki webhook'ları listeler.
        """
        return self._make_request('get', f'/repos/{owner}/{repo}/hooks')
    
    def create_webhook(self, owner, repo, url, secret=None, events=None, active=True):
        """
        Repository için yeni bir webhook oluşturur.
        """
        if events is None:
            events = ['push', 'pull_request', 'issues']
        
        data = {
            'name': 'web',
            'active': active,
            'events': events,
            'config': {
                'url': url,
                'content_type': 'json',
                'insecure_ssl': '0'
            }
        }
        
        if secret:
            data['config']['secret'] = secret
        
        return self._make_request('post', f'/repos/{owner}/{repo}/hooks', data=data)
    
    def delete_webhook(self, owner, repo, hook_id):
        """
        Repository'den bir webhook'u siler.
        """
        return self._make_request('delete', f'/repos/{owner}/{repo}/hooks/{hook_id}')
    
    def get_releases(self, owner, repo, max_releases=None):
        """
        Repository'deki release'leri listeler.
        """
        return self._paginate_request(f'/repos/{owner}/{repo}/releases', max_items=max_releases)
    
    def create_release(self, owner, repo, tag_name, name, body=None, draft=False, prerelease=False):
        """
        Repository için yeni bir release oluşturur.
        """
        data = {
            'tag_name': tag_name,
            'name': name,
            'draft': draft,
            'prerelease': prerelease
        }
        
        if body:
            data['body'] = body
        
        return self._make_request('post', f'/repos/{owner}/{repo}/releases', data=data)
    
    def get_issue_comments(self, owner, repo, issue_number, max_comments=None):
        """
        GitHub issue'daki yorumları alır.
        
        Parametreler:
            owner (str): Repository'nin sahibi
            repo (str): Repository adı
            issue_number (int): Issue numarası
            max_comments (int, optional): Maksimum yorum sayısı
            
        Returns:
            list: Yorumların listesi
        """
        return self._paginate_request(f'/repos/{owner}/{repo}/issues/{issue_number}/comments', max_items=max_comments)
    
    def create_issue_comment(self, owner, repo, issue_number, body):
        """
        GitHub issue'na yeni bir yorum ekler.
        
        Parametreler:
            owner (str): Repository'nin sahibi
            repo (str): Repository adı
            issue_number (int): Issue numarası
            body (str): Yorum içeriği
            
        Returns:
            dict: Oluşturulan yorumun bilgileri
        """
        data = {'body': body}
        return self._make_request('post', f'/repos/{owner}/{repo}/issues/{issue_number}/comments', data=data)
    
    def update_issue_comment(self, owner, repo, comment_id, body):
        """
        GitHub issue yorumunu günceller.
        
        Parametreler:
            owner (str): Repository'nin sahibi
            repo (str): Repository adı
            comment_id (int): Yorum ID'si 
            body (str): Güncellenmiş yorum içeriği
            
        Returns:
            dict: Güncellenen yorumun bilgileri
        """
        data = {'body': body}
        return self._make_request('patch', f'/repos/{owner}/{repo}/issues/comments/{comment_id}', data=data)
    
    def delete_issue_comment(self, owner, repo, comment_id):
        """
        GitHub issue yorumunu siler.
        
        Parametreler:
            owner (str): Repository'nin sahibi
            repo (str): Repository adı
            comment_id (int): Yorum ID'si
            
        Returns:
            None veya hata
        """
        return self._make_request('delete', f'/repos/{owner}/{repo}/issues/comments/{comment_id}') 