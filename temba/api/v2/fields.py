from rest_framework import relations, serializers

from django.contrib.auth.models import User
from django.db.models import Q

from temba.campaigns.models import Campaign, CampaignEvent
from temba.channels.models import Channel
from temba.contacts.models import URN, Contact, ContactField as ContactFieldModel, ContactGroup, ContactURN
from temba.flows.models import Flow
from temba.msgs.models import Label, Msg
from temba.tickets.models import Ticket, Ticketer, Topic
from temba.utils import languages
from temba.utils.uuid import is_uuid

# default maximum number of items in a posted list or dict
DEFAULT_MAX_LIST_ITEMS = 100
DEFAULT_MAX_DICT_ITEMS = 100


def validate_size(value, max_size: int):
    if hasattr(value, "__len__") and len(value) > max_size:
        raise serializers.ValidationError(f"This field can only contain up to {max_size} items.")


def validate_language(value):
    if not isinstance(value, str) or len(value) != 3 or not languages.get_name(value):
        raise serializers.ValidationError("Not an allowed ISO 639-3 language code.")


def validate_translations(value, *, max_length: int, lists: bool, max_items: int = 0):
    if not isinstance(value, dict):
        raise serializers.ValidationError("Must be a dictionary of languages to translated values.")
    elif len(value) == 0:
        raise serializers.ValidationError("Must include at least one translation.")

    for lang, trans in value.items():
        validate_language(lang)

        if lists:
            if not isinstance(trans, list) or not all([isinstance(t, str) for t in trans]):
                raise serializers.ValidationError("Translations must be lists of strings.")

            if len(trans) > max_items:
                raise serializers.ValidationError(f"Translations can only contain up to {max_items} items.")

            as_list = trans
        else:
            if not isinstance(trans, str):
                raise serializers.ValidationError("Translations must be strings.")

            as_list = [trans]

        for t in as_list:
            if not t.strip():
                raise serializers.ValidationError("Translations cannot be empty or blank.")
            if len(t) > max_length:
                raise serializers.ValidationError("Translations must have no more than %d characters." % max_length)


def validate_urn(value, strict=True, country_code=None):
    try:
        normalized = URN.normalize(value, country_code=country_code)

        if strict and not URN.validate(normalized, country_code=country_code):
            raise ValueError()
    except ValueError:
        raise serializers.ValidationError("Invalid URN: %s. Ensure phone numbers contain country codes." % value)
    return normalized


class LanguageField(serializers.CharField):
    max_length = 3

    def to_internal_value(self, data):
        validate_language(data)

        return super().to_internal_value(data)


class TranslationsField(serializers.Field):
    """
    A field which is either a string or a language -> string translations dict
    """

    def __init__(self, max_length, **kwargs):
        self.max_length = max_length

        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = {self.context["org"].flow_languages[0]: data}

        validate_translations(data, max_length=self.max_length, lists=False)

        return data


class TranslationsListField(serializers.Field):
    """
    A field which is either a list of strings or a language -> list of strings translations dict
    """

    def __init__(self, max_items, max_length, **kwargs):
        self.max_items = max_items
        self.max_length = max_length

        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {self.context["org"].flow_languages[0]: data}

        validate_translations(data, max_length=self.max_length, lists=True, max_items=self.max_items)

        return data


class LimitedListField(serializers.ListField):
    """
    A list field which can be only be written to with a limited number of items
    """

    def to_internal_value(self, data):
        validate_size(data, DEFAULT_MAX_LIST_ITEMS)

        return super().to_internal_value(data)


class LimitedDictField(serializers.DictField):
    """
    A dict field which can be only be written to with a limited number of items
    """

    def to_internal_value(self, data):
        validate_size(data, DEFAULT_MAX_DICT_ITEMS)

        return super().to_internal_value(data)


class URNField(serializers.CharField):
    max_length = 255

    def to_representation(self, obj):
        if self.context["org"].is_anon:
            return None
        else:
            return str(obj)

    def to_internal_value(self, data):
        country_code = self.context["org"].default_country_code
        return validate_urn(str(data), country_code=country_code)


class URNListField(LimitedListField):
    child = URNField()


class TembaModelField(serializers.RelatedField):
    model = None
    model_manager = "objects"
    lookup_fields = ("uuid",)

    # lookup fields which should be matched case-insensitively
    ignore_case_for_fields = ()

    # throw validation exception if any object not found, otherwise returns none
    require_exists = True

    class LimitedSizeList(serializers.ManyRelatedField):
        def run_validation(self, data=serializers.empty):
            validate_size(data, DEFAULT_MAX_LIST_ITEMS)

            return super().run_validation(data)

    @classmethod
    def many_init(cls, *args, **kwargs):
        """
        Overridden to provide a custom ManyRelated which limits number of items
        """
        list_kwargs = {"child_relation": cls(*args, **kwargs)}
        for key in kwargs.keys():
            if key in relations.MANY_RELATION_KWARGS:
                list_kwargs[key] = kwargs[key]
        return TembaModelField.LimitedSizeList(**list_kwargs)

    def get_queryset(self):
        manager = getattr(self.model, self.model_manager)
        kwargs = {"org": self.context["org"]}
        if hasattr(self.model, "is_active"):
            kwargs["is_active"] = True
        return manager.filter(**kwargs)

    def get_object(self, value):
        # ignore lookup fields that can't be queryed with the given value
        lookup_fields = []
        for lookup_field in self.lookup_fields:
            if lookup_field != "uuid" or is_uuid(value):
                lookup_fields.append(lookup_field)

        # if we have no possible lookup fields left, there's no matching object
        if not lookup_fields:
            return None  # pragma: no cover

        query = Q()
        for lookup_field in lookup_fields:
            ignore_case = lookup_field in self.ignore_case_for_fields
            lookup = "%s__%s" % (lookup_field, "iexact" if ignore_case else "exact")
            query |= Q(**{lookup: value})

        return self.get_queryset().filter(query).first()

    def to_representation(self, obj):
        return {"uuid": str(obj.uuid), "name": obj.name}

    def to_internal_value(self, data):
        if not (isinstance(data, str) or isinstance(data, int)):
            raise serializers.ValidationError("Must be a string or integer")

        obj = self.get_object(data)

        if self.require_exists and not obj:
            raise serializers.ValidationError("No such object: %s" % data)

        return obj


class CampaignField(TembaModelField):
    model = Campaign

    def get_queryset(self):
        manager = getattr(self.model, self.model_manager)
        return manager.filter(org=self.context["org"], is_active=True, is_archived=False)


class CampaignEventField(TembaModelField):
    model = CampaignEvent

    def get_queryset(self):
        return self.model.objects.filter(campaign__org=self.context["org"], is_active=True)


class ChannelField(TembaModelField):
    model = Channel


class ContactField(TembaModelField):
    model = Contact
    lookup_fields = ("uuid", "urns__urn")

    def __init__(self, as_summary=False, **kwargs):
        self.as_summary = as_summary
        super().__init__(**kwargs)

    def to_representation(self, obj):
        rep = {"uuid": str(obj.uuid), "name": obj.name}
        org = self.context["org"]

        if self.as_summary:
            urn = obj.get_urn()
            if urn:
                urn_str, urn_display = urn.get_for_api(), obj.get_urn_display() if not org.is_anon else None
            else:
                urn_str, urn_display = None, None

            rep.update({"urn": urn_str, "urn_display": urn_display})

            if org.is_anon:
                rep["anon_display"] = obj.anon_display

        return rep

    def get_queryset(self):
        return self.model.objects.filter(org=self.context["org"], is_active=True)

    def get_object(self, value):
        # try to normalize as URN but don't blow up if it's a UUID
        try:
            as_urn = URN.identity(URN.normalize(str(value)))
        except ValueError:
            as_urn = value

        contact_ids_with_urn = list(ContactURN.objects.filter(identity=as_urn).values_list("contact_id", flat=True))

        return self.get_queryset().filter(Q(uuid=value) | Q(id__in=contact_ids_with_urn)).first()


class ContactFieldField(TembaModelField):
    model = ContactFieldModel
    lookup_fields = ("key",)

    def to_representation(self, obj):
        return {
            "key": obj.key,
            "name": obj.name,
            "label": obj.name,  # for backwards compatibility
        }


class ContactGroupField(TembaModelField):
    model = ContactGroup
    lookup_fields = ("uuid", "name")
    ignore_case_for_fields = ("name",)

    def __init__(self, allow_dynamic=True, **kwargs):
        self.allow_dynamic = allow_dynamic
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        obj = super().to_internal_value(data)

        if not self.allow_dynamic and obj.is_smart:
            raise serializers.ValidationError("Contact group must not be query based: %s" % data)

        return obj

    def get_queryset(self):
        return ContactGroup.get_groups(org=self.context["org"])


class FlowField(TembaModelField):
    model = Flow


class LabelField(TembaModelField):
    model = Label
    lookup_fields = ("uuid", "name")
    ignore_case_for_fields = ("name",)


class MessageField(TembaModelField):
    model = Msg
    lookup_fields = ("id",)

    # messages get archived automatically so don't error if a message doesn't exist
    require_exists = False

    def get_queryset(self):
        return self.model.objects.filter(
            org=self.context["org"], visibility__in=(Msg.VISIBILITY_VISIBLE, Msg.VISIBILITY_ARCHIVED)
        )


class TicketerField(TembaModelField):
    model = Ticketer


class TicketField(TembaModelField):
    model = Ticket


class TopicField(TembaModelField):
    model = Topic


class UserField(TembaModelField):
    model = User
    lookup_fields = ("email",)
    ignore_case_for_fields = ("email",)

    def __init__(self, assignable_only=False, **kwargs):
        self.assignable_only = assignable_only
        super().__init__(**kwargs)

    def to_representation(self, obj):
        return {"email": obj.email, "name": obj.name}

    def get_queryset(self):
        org = self.context["org"]
        if self.assignable_only:
            qs = org.get_users(with_perm=Ticket.ASSIGNEE_PERMISSION)
        else:
            qs = org.get_users()

        return qs
