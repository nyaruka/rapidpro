import requests

from ...models import ClassifierType, Intent
from .views import ConnectView


class BothubType(ClassifierType):
    """
    Type for classifiers from Bothub
    """

    CONFIG_ACCESS_TOKEN = "access_token"

    name = "Bothub"
    slug = "bothub"
    icon = "icon-bothub"

    connect_view = ConnectView
    connect_blurb = """
        <a href="https://bothub.it">Bothub</a> is an Open Source NLP platform. It supports 29 languages ​​and is evolving to include the languages ​​and dialects of remote cultures.
        """

    form_blurb = """
        You can find the access token for your bot on the Integration tab.
        """

    INTENT_URL = "https://nlp.bothub.it/info/"

    def get_active_intents_from_api(self, classifier):
        access_token = classifier.config[self.CONFIG_ACCESS_TOKEN]

        try:
            response = requests.get(self.INTENT_URL, headers={"Authorization": f"Bearer {access_token}"})
            response.raise_for_status()

            response_json = response.json()
        except requests.RequestException:
            return []

        intents = []
        for intent in response_json["intents"]:
            intents.append(Intent(name=intent, external_id=intent))

        return intents
