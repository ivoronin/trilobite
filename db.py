# pylint: disable=C0116,C0115,C0114,C0103,R0903
from datetime import datetime, timezone, timedelta
from os import environ
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, UTCDateTimeAttribute
from trello import TrelloClient
import pytz


class UserModel(Model):
    class Meta:
        table_name = environ['USERS_TABLE_NAME']
        region = environ['AWS_DEFAULT_REGION']
    telegram_user_id = NumberAttribute(hash_key=True)
    trello_api_key = UnicodeAttribute(null=False)
    trello_api_token = UnicodeAttribute(null=False)
    trello_board_id = UnicodeAttribute(null=False)
    timezone_name = UnicodeAttribute(null=True, default='UTC')
    context_card_id = UnicodeAttribute(null=True)
    context_updated_at = UTCDateTimeAttribute(null=True)

    @property
    def trello_board(self):
        trello = TrelloClient(api_key=self.trello_api_key, token=self.trello_api_token)
        return trello.get_board(self.trello_board_id)

    @property
    def trello_upcoming_cards(self):
        open_cards = self.trello_board.open_cards()
        incomplete = lambda c: not c.is_due_complete
        active_cards = filter(incomplete, open_cards)
        epoch = datetime.fromtimestamp(0).astimezone(timezone.utc)
        due_date = lambda c: c.due_date or epoch
        return sorted(active_cards, key=due_date)

    @property
    def timezone(self):
        return pytz.timezone(self.timezone_name)

    @property
    def context_is_stale(self):
        stale = False
        if self.context_updated_at is not None:
            utcnow = datetime.now(timezone.utc)
            if utcnow - self.context_updated_at > timedelta(hours=3):
                stale = True
        return stale

    @property
    def context_card(self):
        return self.trello_board.client.get_card(self.context_card_id)

    @context_card.setter
    def context_card(self, card):
        self.context_card_id = card.id if card else None
        self.context_updated_at = datetime.now(timezone.utc)
        self.save()

    @property
    def in_card_context(self):
        return bool(self.context_card_id)
