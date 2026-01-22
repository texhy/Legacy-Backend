"""
WebSocket consumers for real-time chat with AI integration.
"""
import json
import asyncio
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from apps.accounts.authentication import CustomJWTAuthentication
from apps.libraries.models import Library, Chapter

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for chat functionality.
    Handles real-time messaging between user and AI.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        # Get JWT token from query string
        query_string = self.scope.get('query_string', b'').decode()
        token = None
        
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=')[1]
                break
        
        if not token:
            await self.close()
            return
        
        # Authenticate user
        self.user = await self.authenticate_user(token)
        if not self.user:
            await self.close()
            return
        
        # Store chapter_id from scope (will be set on join command)
        self.chapter_id = None
        self.chapter_group_name = None
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': 'Connected to Legacy chat',
            'status': 'connected'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.chapter_group_name:
            await self.channel_layer.group_discard(
                self.chapter_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle messages received from WebSocket."""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'message': 'pong'
                }))
            
            elif command == 'join':
                await self.handle_join(data)
            
            elif command == 'message':
                await self.handle_message(data)
            
            elif command == 'typing':
                await self.handle_typing(data)
            
            elif command == 'leave':
                await self.handle_leave()
            
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown command: {command}'
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            # #region agent log
            import traceback as _tb; open('/home/hassan/Desktop/Classic SH/AI Journal Workflow/backend/.cursor/debug.log', 'a').write(json.dumps({"location": "consumers.py:receive:exception", "message": "Exception in receive", "data": {"error": str(e), "traceback": _tb.format_exc()}, "hypothesisId": "D", "timestamp": __import__('time').time()}) + '\n')
            # #endregion
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error: {str(e)}'
            }))
    
    async def handle_join(self, data):
        """Handle join chapter command."""
        # #region agent log
        import json as _json; open('/home/hassan/Desktop/Classic SH/AI Journal Workflow/backend/.cursor/debug.log', 'a').write(_json.dumps({"location": "consumers.py:handle_join:entry", "message": "handle_join called", "data": {"data": str(data)}, "hypothesisId": "B", "timestamp": __import__('time').time()}) + '\n')
        # #endregion
        chapter_id = data.get('chapter_id')
        
        if not chapter_id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'chapter_id required'
            }))
            return
        
        # #region agent log
        open('/home/hassan/Desktop/Classic SH/AI Journal Workflow/backend/.cursor/debug.log', 'a').write(_json.dumps({"location": "consumers.py:handle_join:before_verify", "message": "About to call verify_and_get_chapter_info", "data": {"chapter_id": str(chapter_id), "user_id": str(self.user.id)}, "hypothesisId": "C", "timestamp": __import__('time').time()}) + '\n')
        # #endregion
        # Verify user owns this chapter and get all needed info in one call
        result = await self.verify_and_get_chapter_info(chapter_id, self.user.id)
        if not result:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Chapter not found or access denied'
            }))
            return
        
        chapter_title, library_id = result
        
        # Leave previous chapter group if any
        if self.chapter_group_name:
            await self.channel_layer.group_discard(
                self.chapter_group_name,
                self.channel_name
            )
        
        # Join new chapter group
        self.chapter_id = chapter_id
        self.library_id = library_id
        self.chapter_group_name = f'chat_{chapter_id}'
        
        await self.channel_layer.group_add(
            self.chapter_group_name,
            self.channel_name
        )
        
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': f'Joined chapter: {chapter_title}',
            'chapter_id': str(chapter_id),
            'library_id': self.library_id
        }))
    
    async def handle_message(self, data):
        """Handle chat message command - processes through AI and returns response."""
        if not self.chapter_id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Must join a chapter first'
            }))
            return
        
        content = data.get('content', '').strip()
        if not content:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Message content cannot be empty'
            }))
            return
        
        timestamp = datetime.now().isoformat()
        
        # 1. Echo user message back immediately
        await self.send(text_data=json.dumps({
            'type': 'message',
            'sender': 'USER',
            'content': content,
            'user_id': str(self.user.id),
            'timestamp': timestamp
        }))
        
        # 2. Send AI typing indicator
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender': 'AI',
            'is_typing': True
        }))
        
        try:
            # 3. Process through AI chat graph
            ai_result = await self.process_ai_message(
                user_message=content,
                chapter_id=str(self.chapter_id),
                library_id=self.library_id,
                user_id=str(self.user.id)
            )
            
            # 4. Send AI response
            await self.send(text_data=json.dumps({
                'type': 'message',
                'sender': 'AI',
                'content': ai_result['ai_response'],
                'metadata': ai_result.get('metadata', {}),
                'message_id': ai_result.get('ai_message_id'),
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            # Send error message
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'AI processing error: {str(e)}'
            }))
        
        finally:
            # 5. Stop AI typing indicator
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'sender': 'AI',
                'is_typing': False
            }))
    
    async def handle_typing(self, data):
        """Handle typing indicator."""
        if not self.chapter_id:
            return
        
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.chapter_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'is_typing': is_typing
            }
        )
    
    async def handle_leave(self):
        """Handle leave chapter command."""
        if self.chapter_group_name:
            await self.channel_layer.group_discard(
                self.chapter_group_name,
                self.channel_name
            )
            self.chapter_id = None
            self.chapter_group_name = None
            
            await self.send(text_data=json.dumps({
                'type': 'system',
                'message': 'Left chapter'
            }))
    
    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'sender': event['sender'],
            'content': event['content'],
            'user_id': event.get('user_id'),
            'timestamp': event.get('timestamp')
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'is_typing': event['is_typing']
        }))
    
    @database_sync_to_async
    def authenticate_user(self, token):
        """Authenticate user from JWT token."""
        try:
            auth = CustomJWTAuthentication()
            validated_token = auth.get_validated_token(token)
            user = auth.get_user(validated_token)
            return user
        except Exception:
            return None
    
    @database_sync_to_async
    def verify_and_get_chapter_info(self, chapter_id, user_id):
        """Verify chapter exists, user owns it, and return title and library_id."""
        # #region agent log
        import json as _json; open('/home/hassan/Desktop/Classic SH/AI Journal Workflow/backend/.cursor/debug.log', 'a').write(_json.dumps({"location": "consumers.py:verify_and_get_chapter_info:entry", "message": "Entering verify_and_get_chapter_info", "data": {"chapter_id": str(chapter_id), "user_id": str(user_id)}, "hypothesisId": "A", "timestamp": __import__('time').time()}) + '\n')
        # #endregion
        try:
            chapter = Chapter.objects.select_related('library').get(id=chapter_id)
            # #region agent log
            open('/home/hassan/Desktop/Classic SH/AI Journal Workflow/backend/.cursor/debug.log', 'a').write(_json.dumps({"location": "consumers.py:verify_and_get_chapter_info:after_query", "message": "Chapter fetched successfully", "data": {"chapter_title": chapter.title, "library_user_id": str(chapter.library.user_id)}, "hypothesisId": "A", "timestamp": __import__('time').time()}) + '\n')
            # #endregion
            # Check ownership
            if chapter.library.user_id != user_id:
                return None
            # Return title and library_id
            return (chapter.title, str(chapter.library_id))
        except Chapter.DoesNotExist:
            # #region agent log
            open('/home/hassan/Desktop/Classic SH/AI Journal Workflow/backend/.cursor/debug.log', 'a').write(_json.dumps({"location": "consumers.py:verify_and_get_chapter_info:not_found", "message": "Chapter not found", "data": {"chapter_id": str(chapter_id)}, "hypothesisId": "A", "timestamp": __import__('time').time()}) + '\n')
            # #endregion
            return None
    
    @database_sync_to_async
    def get_chapter(self, chapter_id):
        """Get chapter by ID with library preloaded."""
        try:
            return Chapter.objects.select_related('library').get(id=chapter_id)
        except Chapter.DoesNotExist:
            return None
    
    @database_sync_to_async
    def process_ai_message(self, user_message: str, chapter_id: str, library_id: str, user_id: str):
        """Process message through AI chat graph."""
        from apps.ai.graphs.chat_graph import process_chat_message
        
        # This is a synchronous function that will be called from async context
        # The chat_graph.process_chat_message is synchronous, so this wrapper is correct
        return process_chat_message(
            user_message=user_message,
            chapter_id=chapter_id,
            library_id=library_id,
            user_id=user_id
        )