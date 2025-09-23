from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
import json
import requests
import logging
import os
import subprocess
import tempfile
import traceback
import unicodedata
import re

from .models import ChatSession, ChatMessage, OllamaSettings
from .forms import OllamaSettingsForm

logger = logging.getLogger(__name__)

# Bridge script path
BRIDGE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ollama_bridge.py')

def ai_required(view_func):
    """
    Decorator to check if user has 'ai' tag for AI module access.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        # Check if user has 'ai' tag
        if not hasattr(request.user, 'tags') or not request.user.tags.filter(name='ai').exists():
            messages.error(request, 'AI modülüne erişim için "ai" etiketine sahip olmanız gerekmektedir.')
            return HttpResponseForbidden('AI modülüne erişim yetkiniz bulunmamaktadır.')
        
        return view_func(request, *args, **kwargs)
    return wrapper

# Ollama API endpoints - Local Ollama server
OLLAMA_ENDPOINTS = [
    "http://localhost:11434/api/generate",  # Local Ollama server
    "http://127.0.0.1:11434/api/generate",  # Alternative local address
]

# API bilgileri
API_INFO = {
    'ollama': {
        'name': 'Ollama API',
        'description': 'Yerel Ollama server ile AI model entegrasyonu',
        'endpoints': [
            {
                'name': 'Generate',
                'url': '/api/generate',
                'method': 'POST',
                'description': 'AI model ile sohbet'
            },
            {
                'name': 'Tags',
                'url': '/api/tags',
                'method': 'GET',
                'description': 'Mevcut modelleri listele'
            },
            {
                'name': 'Pull',
                'url': '/api/pull',
                'method': 'POST',
                'description': 'Model indir'
            }
        ],
        'default_port': 11434
    }
}

def fix_turkish_encoding(text):
    """
    Türkçe karakterlerin encoding hatalarını düzeltir.
    """
    if not isinstance(text, str):
        return text
    
    # Yöntem 1: Latin-1'den UTF-8'e çevirme dene
    try:
        fixed_text = text.encode('latin1').decode('utf-8')
        if '?' not in fixed_text and '' not in fixed_text:
            text = fixed_text
    except Exception:
        pass
    
    # Yöntem 2: Unicodedata normalizasyon
    try:
        fixed_text = unicodedata.normalize('NFKD', text)
        if '?' not in fixed_text and '' not in fixed_text:
            text = fixed_text
    except Exception:
        pass
    
    # Yaygın hatalı Türkçe karakter kodlamalarını düzelt
    replacements = {
        'takže': 'takže',
        'diliyorum': 'diliyorum',
        'hissetmiyorum': 'hissetmiyorum',
        'gerçekten': 'gerçekten',
        'yapabilirmi': 'yapabilir miyim',
        'ï¿½': 'ı',
        'Ä°': 'İ',
        'Ä±': 'ı',
        'ÄŸ': 'ğ',
        'Å': 'ş',
        'ÅŸ': 'ş',
        'Ã§': 'ç',
        'Ã¶': 'ö',
        'Ã¼': 'ü',
        'Ã': 'Ğ',
        'Ì¸': 'ş',
        'ÅŸ': 'ş',
        'ÅŠ': 'Ş',
        'Ã‡': 'Ç',
        'Ã–': 'Ö',
        'Ãœ': 'Ü',
        'ÄŒ': 'Ğ',
        'Ã˜': 'İ',
        'Ã¯': 'İ',
        'Ã™': 'Ü',
        'Å€': 'Ş'
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    
    # Bozuk karakterleri temizleme - son çare
    if '?' in text or '' in text:
        # Bozuk karakter tespiti
        text = re.sub(r'[^\x00-\x7F]+\?', '', text)  # Soru işareti ile biten non-ASCII blokları temizle
        text = re.sub(r'\?[^\x00-\x7F]+', '', text)  # Soru işareti ile başlayan non-ASCII blokları temizle
        
    return text

def clean_ai_response(response_text):
    """
    AI yanıtlarındaki sadece <think> bölümlerini temizler.
    """
    if not response_text:
        return "Merhaba! Size nasıl yardımcı olabilirim?"
    
    import re
    
    # Sadece <think> bölümlerini temizle (tek satır veya çok satır)
    think_pattern = r'<think>.*?</think>'
    response_text = re.sub(think_pattern, '', response_text, flags=re.DOTALL | re.IGNORECASE)
    
    # Kalan boşlukları temizle
    response_text = response_text.strip()
    
    return response_text

@login_required
@ai_required
@ensure_csrf_cookie
def chat_list(request):
    """View to list all chat sessions for the current user."""
    sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'chatbot/chat_list.html', {'sessions': sessions})

@login_required
@ai_required
@ensure_csrf_cookie
def chat_session(request, session_id=None):
    """View to handle a specific chat session or create a new one."""
    if request.method == 'POST':
        # Handle model update
        try:
            data = json.loads(request.body)
            if data.get('action') == 'update_model':
                session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
                new_model = data.get('ai_model')
                if new_model in [choice[0] for choice in ChatSession.MODEL_CHOICES]:
                    session.ai_model = new_model
                    session.save()
                    return JsonResponse({'success': True})
                else:
                    return JsonResponse({'success': False, 'error': 'Invalid model'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    if session_id:
        session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    else:
        # Create a new chat session
        session = ChatSession.objects.create(
            user=request.user,
            title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            language='tr',
            ai_model='deepseek-r1:8b'  # Default model
        )
        
    messages = ChatMessage.objects.filter(session=session)
    return render(request, 'chatbot/chat_session.html', {
        'session': session,
        'messages': messages
    })

@login_required
@ai_required
def delete_session(request, session_id):
    """View to delete a chat session."""
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    session.delete()
    return redirect('chatbot:chat_list')

@login_required
@ai_required
def rename_session(request, session_id):
    """View to rename a chat session."""
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    
    if request.method == 'POST':
        new_title = request.POST.get('title')
        if new_title:
            session.title = new_title
            session.save()
    
    return redirect('chatbot:chat_session', session_id=session.id)

@login_required
@ai_required
@require_POST
def send_message(request):
    """API endpoint to send a message to the AI and get a response."""
    logger.info("send_message view called")
    
    try:
        # CSRF kontrolü - genelde Django otomatik yapar, ama hata ayıklama için ekstra kontrol
        csrf_token = request.headers.get('X-CSRFToken')
        if not csrf_token:
            logger.warning("CSRF token is missing in request headers")
            # CSRF token eksikse, hatayı logla ama işleme devam et (Django zaten gerekli kontrolü yapar)
        else:
            logger.info(f"CSRF token found in request (length: {len(csrf_token)})")
        
        # Detaylı istek loglaması ekle
        logger.info(f"Request method: {request.method}")
        logger.info(f"Content type: {request.content_type}")
        logger.info(f"POST data: {dict(request.POST)}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Request body'yi bir kez oku ve sakla
        session_id = None
        message = None
        request_body = None
        
        # JSON verisi olarak parsing
        if request.content_type == 'application/json' or 'json' in request.content_type.lower():
            try:
                request_body = request.body
                logger.info(f"Raw body length: {len(request_body) if request_body else 0}")
                
                if request_body:
                    data = json.loads(request_body)
                    session_id = data.get('session_id')
                    # String olarak session_id geliyorsa int'e çevir
                    if session_id and isinstance(session_id, str) and session_id.isdigit():
                        session_id = int(session_id)
                    
                    message = data.get('message')
                    logger.info(f"JSON data received: session_id={session_id} (type: {type(session_id)}), message={message[:20] if message else None}...")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON body: {str(e)}")
                if request_body:
                    logger.warning(f"Raw body content: {request_body.decode('utf-8', errors='replace')[:200]}")
        
        # POST form verisi olarak parsing
        if not session_id or not message:
            session_id = request.POST.get('session_id')
            # String olarak session_id geliyorsa int'e çevir
            if session_id and isinstance(session_id, str) and session_id.isdigit():
                session_id = int(session_id)
                
            message = request.POST.get('message')
            logger.info(f"Form data received: session_id={session_id} (type: {type(session_id)}), message={message[:20] if message else None}...")
        
        # Session ID ve message kontrolü
        if not session_id:
            logger.error("Missing session_id parameter")
            return JsonResponse({
                'error': 'Missing required parameter: session_id is required',
                'received_data': {
                    'session_id': session_id,
                    'message': message,
                    'has_body': bool(request_body),
                    'raw_body': request_body.decode('utf-8', errors='replace')[:200] if request_body else None,
                    'content_type': request.content_type,
                    'method': request.method,
                    'POST': dict(request.POST),
                    'headers': dict(request.headers),
                }
            }, status=400)
            
        if not message:
            logger.error("Missing message parameter")
            return JsonResponse({
                'error': 'Missing required parameter: message is required',
                'received_data': {
                    'session_id': session_id,
                    'message': message,
                    'has_body': bool(request_body),
                    'raw_body': request_body.decode('utf-8', errors='replace')[:200] if request_body else None,
                    'content_type': request.content_type,
                    'method': request.method,
                    'POST': dict(request.POST),
                    'headers': dict(request.headers),
                }
            }, status=400)
        
        # Get the session
        try:
            # Session ID tipini kontrol et
            if not isinstance(session_id, int):
                try:
                    session_id = int(session_id)
                    logger.info(f"Converted session_id to int: {session_id}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to convert session_id to int: {str(e)}")
                    return JsonResponse({
                        'error': f'Invalid session_id format: {session_id} - must be an integer',
                        'received_data': {
                            'session_id': session_id,
                            'session_id_type': type(session_id).__name__,
                        }
                    }, status=400)
            
            # Session'ı veritabanından al
            try:
                session = ChatSession.objects.get(pk=session_id, user=request.user)
                logger.info(f"Session found: {session.title}")
            except ChatSession.DoesNotExist:
                logger.error(f"Session not found with ID: {session_id}")
                
                # Otomatik olarak yeni bir session oluştur
                new_session = ChatSession.objects.create(
                    user=request.user,
                    title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                    language='tr'
                )
                logger.info(f"Created new session automatically: {new_session.id}")
                
                return JsonResponse({
                    'error': f'Session not found with ID: {session_id}. A new session was created instead.',
                    'new_session_id': new_session.id,
                    'new_session_title': new_session.title
                }, status=404)
        except Exception as e:
            logger.error(f"Error retrieving session: {str(e)}")
            return JsonResponse({'error': f'Error retrieving session: {str(e)}'}, status=500)
        
        # Save the user message
        user_message = ChatMessage.objects.create(
            session=session,
            sender='user',
            content=message
        )
        logger.info(f"User message saved: {user_message.id}")
        
        # Update session timestamp
        session.save()  # This will update the updated_at field
        
        # Get user context information for improved personalization
        user_context = {
            'username': request.user.username,
            'full_name': request.user.get_full_name(),
            'role': getattr(request.user, 'role', 'Not provided'),
            'department': getattr(request.user, 'department', 'Not provided'),
            'email': request.user.email
        }
        
        # Yeni Ollama API'ye istek gönder (http://[server]:5252/ask)
        ai_response = None
        last_error = None
        
        try:
            # Kullanıcının Ollama ayarlarını al
            try:
                ollama_settings = OllamaSettings.objects.get(user=request.user, is_active=True)
                api_url = f"{ollama_settings.api_url}/api/generate"
                logger.info(f"Using user's Ollama settings: {api_url}")
            except OllamaSettings.DoesNotExist:
                # Varsayılan endpoint kullan
                api_url = OLLAMA_ENDPOINTS[0]  # localhost:11434
                logger.info(f"Using default Ollama API: {api_url}")
            
            # Session'dan model bilgisini al, yoksa varsayılan modeli kullan
            selected_model = session.ai_model
            selected_language = session.language  # Session'dan dil bilgisini al
            
            if not selected_model or selected_model not in ['gemma3:4b', 'deepseek-r1:8b']:
                # Kullanıcının varsayılan modelini kontrol et
                try:
                    ollama_settings = OllamaSettings.objects.get(user=request.user, is_active=True)
                    if ollama_settings.default_model:
                        selected_model = ollama_settings.default_model
                        logger.info(f"Using user's default model: {selected_model}")
                    else:
                        # Mevcut modelleri al ve ilkini kullan
                        available_models = ollama_settings.get_available_models()
                        if available_models:
                            selected_model = available_models[0]
                            logger.info(f"Using first available model: {selected_model}")
                        else:
                            selected_model = 'gemma3:4b'  # Fallback
                            logger.info(f"Using fallback model: {selected_model}")
                    
                    # Dil bilgisini de ayarlardan al
                    if not selected_language:
                        selected_language = ollama_settings.default_language
                        logger.info(f"Using user's default language: {selected_language}")
                        
                except OllamaSettings.DoesNotExist:
                    selected_model = 'gemma3:4b'  # Fallback
                    selected_language = 'tr'  # Fallback dil
                    logger.info(f"Using fallback model: {selected_model} and language: {selected_language}")
            
            # Dil bilgisi yoksa varsayılan olarak Türkçe
            if not selected_language:
                selected_language = 'tr'
            
            logger.info(f"Final AI model: {selected_model}, language: {selected_language}")
            
            # Dil talimatlarını hazırla
            language_instructions = {
                'tr': 'ÖNEMLİ: Sadece Türkçe yanıt verin. Türkçe dışında hiçbir dilde yanıt vermeyin. Kullanıcıyla Türkçe iletişim kurun.',
                'en': 'IMPORTANT: Respond only in English. Do not respond in any other language. Communicate with the user in English.',
                'fr': 'IMPORTANT: Répondez uniquement en français. Ne répondez dans aucune autre langue. Communiquez avec l\'utilisateur en français.',
                'de': 'WICHTIG: Antworten Sie nur auf Deutsch. Antworten Sie in keiner anderen Sprache. Kommunizieren Sie mit dem Benutzer auf Deutsch.'
            }
            
            # Chat geçmişini al (son 10 mesaj)
            recent_messages = ChatMessage.objects.filter(session=session).order_by('-timestamp')[:10]
            
            # Context oluştur
            context_parts = []
            for msg in reversed(recent_messages):  # Eski mesajlardan yeniye doğru
                if msg.sender == 'user':
                    context_parts.append(f"Kullanıcı: {msg.content}")
                else:
                    context_parts.append(f"AI: {msg.content}")
            
            # Mevcut mesajı ekle
            context_parts.append(f"Kullanıcı: {message}")
            
            # Context'i birleştir
            context = "\n".join(context_parts)
            
            # Dil talimatını ekle
            language_prompt = f"{language_instructions.get(selected_language, language_instructions['tr'])}\n\n{context}"
            
            # API isteği hazırla
            api_payload = {
                "model": selected_model,
                "prompt": language_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2000
                }
            }
            
            # API isteği gönder
            response = requests.post(
                api_url,
                headers={"Content-Type": "application/json"},
                json=api_payload,
                timeout=90
            )
            
            # Yanıtı kontrol et
            if response.status_code == 200:
                try:
                    api_data = response.json()
                    logger.info(f"API response received: {api_data}")
                    
                    # Yanıtı al (Ollama API'den 'response' anahtarında)
                    ai_response = api_data.get('response')
                    if ai_response:
                        logger.info("Successfully received response from Ollama API")
                        
                        # Yanıtı temizle
                        ai_response = clean_ai_response(ai_response)
                    else:
                        logger.warning("API response doesn't contain 'response' field")
                        ai_response = f"API yanıtında 'response' alanı bulunamadı. API yanıtı: {api_data}"
                except ValueError as json_error:
                    logger.error(f"JSON parsing error: {json_error}")
                    ai_response = f"API'den gelen yanıt işlenemedi: {str(json_error)}"
            else:
                error_message = f"API request failed with status code: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_message += f" - {error_data['error']}"
                    elif 'error_message' in error_data:
                        error_message += f" - {error_data['error_message']}"
                except:
                    error_message += f" - Response: {response.text[:100]}"
                
                logger.error(error_message)
                last_error = error_message
                ai_response = f"API isteği başarısız oldu: {error_message}"
                
        except Exception as e:
            logger.error(f"Error sending request to Ollama API: {str(e)}")
            last_error = str(e)
            ai_response = f"API'ye erişirken bir hata oluştu: {str(e)}"
        
        # Her durumda son bir karakter düzeltmesi yap
        try:
            ai_response = fix_turkish_encoding(ai_response)
        except Exception as e:
            logger.warning(f"Final encoding fix failed: {str(e)}")
        
        # Save the AI response
        assistant_message = ChatMessage.objects.create(
            session=session,
            sender='assistant',
            content=ai_response
        )
        logger.info(f"Assistant message saved: {assistant_message.id}")
        
        return JsonResponse({
            'user_message': {
                'id': user_message.id,
                'content': user_message.content,
                'timestamp': user_message.timestamp.isoformat()
            },
            'assistant_message': {
                'id': assistant_message.id,
                'content': assistant_message.content,
                'timestamp': assistant_message.timestamp.isoformat()
            }
        })
            
    except Exception as e:
        logger.exception(f"Unexpected error in send_message view: {str(e)}")
        error_traceback = traceback.format_exc()
        logger.error(f"Traceback: {error_traceback}")
        return JsonResponse({
            'error': str(e),
            'traceback': error_traceback,
            'info': "Bir hata oluştu. Lütfen sistem yöneticisiyle iletişime geçin."
        }, status=500)

@login_required
@ai_required
@ensure_csrf_cookie
def chat_widget(request):
    """View to render just the chat widget for embedding in other pages."""
    # Get the most recent session or create a new one
    session = ChatSession.objects.filter(user=request.user).order_by('-updated_at').first()
    
    if not session:
        session = ChatSession.objects.create(
            user=request.user,
            title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            language='tr',
            ai_model='deepseek-r1:8b'  # Default model
        )
        logger.info(f"Created new chat session for widget: {session.id}")
    else:
        logger.info(f"Using existing chat session for widget: {session.id}")
    
    messages = ChatMessage.objects.filter(session=session)
    
    # AJAX isteği kontrolü
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'session_id': session.id,
            'session_title': session.title,
            'messages_count': messages.count()
        })
    
    return render(request, 'chatbot/chat_widget.html', {
        'session': session,
        'messages': messages
    })

@login_required
@ai_required
def get_session(request):
    """API endpoint to get or create a session for the user."""
    try:
        logger.info("get_session API endpoint called")
        
        # Get the most recent session or create a new one
        session = ChatSession.objects.filter(user=request.user).order_by('-updated_at').first()
        
        if not session:
            session = ChatSession.objects.create(
                user=request.user,
                title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                language='tr',
                ai_model='deepseek-r1:8b'  # Default model
            )
            logger.info(f"Created new chat session via API: {session.id}")
        else:
            logger.info(f"Using existing chat session via API: {session.id}")
        
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'session_title': session.title
        })
        
    except Exception as e:
        logger.exception(f"Error in get_session API: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@ai_required
def get_chat_history(request):
    """API endpoint to get chat history for a specific session.
    Implements the '/history' functionality in the API documentation.
    """
    try:
        logger.info("get_chat_history API endpoint called")
        
        # Get session_id from query parameters
        session_id = request.GET.get('session_id')
        
        if not session_id:
            # If no session_id provided, use the most recent session
            session = ChatSession.objects.filter(user=request.user).order_by('-updated_at').first()
            if not session:
                return JsonResponse({
                    'success': False,
                    'error': 'No chat sessions found for this user'
                }, status=404)
        else:
            # Try to convert session_id to int
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid session_id format: {session_id}'
                }, status=400)
            
            # Get the session
            try:
                session = ChatSession.objects.get(pk=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Session not found with ID: {session_id}'
                }, status=404)
        
        # Get messages for the session
        messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
        
        # Format messages according to API documentation
        history = []
        for msg in messages:
            history.append({
                'is_user': msg.sender == 'user',
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'session_title': session.title,
            'history': history
        })
        
    except Exception as e:
        logger.exception(f"Error in get_chat_history API: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@ai_required
@require_POST
def clear_chat_history(request):
    """API endpoint to clear chat history for a specific session.
    Implements the '/clear_history' functionality in the API documentation.
    """
    try:
        logger.info("clear_chat_history API endpoint called")
        
        # Get session_id from request
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                session_id = data.get('session_id')
            except json.JSONDecodeError:
                session_id = None
        else:
            session_id = request.POST.get('session_id')
        
        if not session_id:
            # If no session_id provided, use the most recent session
            session = ChatSession.objects.filter(user=request.user).order_by('-updated_at').first()
            if not session:
                return JsonResponse({
                    'success': False,
                    'message': 'No chat sessions found for this user'
                }, status=404)
        else:
            # Try to convert session_id to int
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'message': f'Invalid session_id format: {session_id}'
                }, status=400)
            
            # Get the session
            try:
                session = ChatSession.objects.get(pk=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': f'Session not found with ID: {session_id}'
                }, status=404)
        
        # Clear messages for the session
        deleted_count, _ = ChatMessage.objects.filter(session=session).delete()
        
        # Return success response
        return JsonResponse({
            'success': True,
            'message': f'Chat history cleared. {deleted_count} messages deleted.',
            'session_id': session.id
        })
        
    except Exception as e:
        logger.exception(f"Error in clear_chat_history API: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error clearing chat history: {str(e)}'
        }, status=500)

@login_required
@ai_required
def ollama_settings(request):
    """
    Kullanıcının Ollama API ayarlarını yönetir
    """
    try:
        # Kullanıcının Ollama ayarlarını al veya oluştur
        ollama_settings, created = OllamaSettings.objects.get_or_create(
            user=request.user,
            defaults={
                'api_url': 'http://localhost:11434',
                'default_model': '',
                'is_active': True
            }
        )
        
        if request.method == 'POST':
            form = OllamaSettingsForm(request.POST, instance=ollama_settings)
            if form.is_valid():
                form.save()
                messages.success(request, 'Ollama ayarlarınız başarıyla kaydedildi.')
                return redirect('chatbot:ollama_settings')
        else:
            form = OllamaSettingsForm(instance=ollama_settings)
        
        # API bağlantı testi
        api_test_result = None
        if request.GET.get('test') == '1':
            api_test_result = test_ollama_connection(ollama_settings.api_url)
        
        # Mevcut modelleri al
        available_models = ollama_settings.get_available_models()
        
        context = {
            'form': form,
            'ollama_settings': ollama_settings,
            'api_test_result': api_test_result,
            'api_info': API_INFO,
            'ollama_endpoints': OLLAMA_ENDPOINTS,
            'available_models': available_models,
        }
        
        return render(request, 'chatbot/ollama_settings.html', context)
        
    except Exception as e:
        logger.exception(f"Error in ollama_settings: {str(e)}")
        messages.error(request, f'Ayarlar yüklenirken hata oluştu: {str(e)}')
        return redirect('chatbot:chat_list')

def test_ollama_connection(api_url):
    """
    Ollama API bağlantısını test eder
    """
    try:
        import requests
        
        # API URL'yi düzenle
        if not api_url.endswith('/api/tags'):
            if api_url.endswith('/'):
                test_url = f"{api_url}api/tags"
            else:
                test_url = f"{api_url}/api/tags"
        else:
            test_url = api_url
            
        response = requests.get(test_url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            return {
                'success': True,
                'message': f'Bağlantı başarılı! {len(models)} model bulundu.',
                'models': [model.get('name', 'Bilinmeyen') for model in models[:5]]  # İlk 5 model
            }
        else:
            return {
                'success': False,
                'message': f'API yanıt vermedi. HTTP {response.status_code}'
            }
            
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'message': 'Bağlantı kurulamadı. IP adresini ve portu kontrol edin.'
        }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'message': 'Bağlantı zaman aşımına uğradı. Ollama server çalışıyor mu?'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Test sırasında hata: {str(e)}'
        }
