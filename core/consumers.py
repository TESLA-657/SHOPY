import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import MessageNegociation, ChatMessage, Client, Vendeur

logger = logging.getLogger(__name__)


class NegociationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.negociation_id = self.scope['url_route']['kwargs']['negociation_id']
        self.group_name = f'negociation_{self.negociation_id}'

        user = self.scope.get('user')
        logger.info(f"WebSocket connect attempt for negociation_id={self.negociation_id}, user={user}")
        
        if not user or not user.is_authenticated:
            logger.warning(f"WebSocket auth failed for negociation_id={self.negociation_id}")
            await self.close()
            return

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(f"WebSocket connected successfully: negociation_id={self.negociation_id}")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await self.accept()  # Accept anyway so client can handle errors
            await self.send(text_data=json.dumps({'error': str(e)}))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        payload = json.loads(text_data)

        raw_message = payload.get('message')
        message_text = (raw_message or '').strip()

        raw_prix = payload.get('prix_propose')
        prix_propose = self.normalize_prix(raw_prix)

        # Autoriser message texte OU proposition de prix seule
        if not message_text and prix_propose is None:
            return

        neg = await self.get_negociation()
        if not await self.user_belongs_to_negociation(neg):
            return

        sender_type = self.normalize_sender_type(payload.get('sender_type'))

        msg = await self.create_chat_message(
            neg=neg,
            sender_type=sender_type,
            content=message_text,
            prix_propose=prix_propose,
        )

        await self.update_negociation_read_state(neg=neg, sender_type=sender_type)

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.message',
                'message': {
                    'id': msg.id,
                    'sender_type': msg.sender_type,
                    'content': msg.content,
                    'prix_propose': msg.prix_propose,
                    'created_at': msg.created_at.isoformat(),
                }
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'message': event['message']}))

    @database_sync_to_async
    def get_negociation(self):
        try:
            return MessageNegociation.objects.select_related('vendeur', 'produit').get(pk=self.negociation_id)
        except MessageNegociation.DoesNotExist:
            return None

    @database_sync_to_async
    def user_belongs_to_negociation(self, neg):
        user = self.scope.get('user')
        if not neg or not user or not user.is_authenticated:
            return False

        # vendeur = owner
        try:
            vendeur = Vendeur.objects.get(user=user)
            if neg.vendeur_id == vendeur.id:
                return True
        except Vendeur.DoesNotExist:
            pass

        # client = by numero (same logic que vos pages)
        try:
            client = Client.objects.get(user=user)
            if neg.client_numero == client.numero:
                return True
        except Client.DoesNotExist:
            pass

        return False

    def normalize_sender_type(self, sender_type):
        return sender_type if sender_type in ('client', 'vendeur') else 'client'

    def normalize_prix(self, prix_value):
        if prix_value in (None, ''):
            return None
        try:
            prix_int = int(prix_value)
            return prix_int if prix_int >= 0 else None
        except (TypeError, ValueError):
            return None

    @database_sync_to_async
    def create_chat_message(self, neg, sender_type, content, prix_propose=None):
        # Persistance DB obligatoire pour conserver l'historique visible
        return ChatMessage.objects.create(
            negociation=neg,
            sender_type=sender_type,
            content=content or '',
            prix_propose=prix_propose,
        )

    @database_sync_to_async
    def update_negociation_read_state(self, neg, sender_type):
        if sender_type == 'client':
            neg.vendor_lu = False
            neg.client_lu = True
        else:
            neg.vendor_lu = True
            neg.client_lu = False
        neg.save(update_fields=['vendor_lu', 'client_lu'])


# Alias pour routing
negociation_consumer = NegociationConsumer

