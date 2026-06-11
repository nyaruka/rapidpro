from datetime import timezone as tzone

from rest_framework import serializers

from temba.ai.models import LLM, KnowledgeBase
from temba.locations.models import AdminBoundary
from temba.orgs.models import Org
from temba.templates.models import Template, TemplateTranslation
from temba.tickets.models import Shortcut


class ModelAsJsonSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        # Pass the DRF serializer context through so model as_json
        # methods can resolve permission/retention-gated fields
        # (e.g. Msg.as_json uses context["user"] / context["org"]
        # for the channel-log link).
        return instance.as_json(context=self.context)


class LLMReadSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="llm_type")
    roles = serializers.SerializerMethodField()

    def get_roles(self, obj):
        return [LLM.ROLE_NAMES[r] for r in obj.roles]

    class Meta:
        model = LLM
        fields = ("uuid", "name", "type", "roles")


class KnowledgeBaseReadSerializer(serializers.ModelSerializer):
    TYPES = {
        KnowledgeBase.TYPE_WEBSITE: "website",
        KnowledgeBase.TYPE_DOCUMENTS: "documents",
        KnowledgeBase.TYPE_FAQ: "faq",
    }
    STATUSES = {
        KnowledgeBase.STATUS_PENDING: "pending",
        KnowledgeBase.STATUS_PROCESSING: "processing",
        KnowledgeBase.STATUS_COMPLETE: "complete",
        KnowledgeBase.STATUS_FAILED: "failed",
    }

    type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def get_type(self, obj):
        return self.TYPES[obj.kb_type]

    def get_status(self, obj):
        return self.STATUSES[obj.status]

    class Meta:
        model = KnowledgeBase
        fields = ("uuid", "name", "type", "status")


class LocationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminBoundary
        fields = ("osm_id", "name", "path")


class ShortcutReadSerializer(serializers.ModelSerializer):
    modified_on = serializers.DateTimeField(default_timezone=tzone.utc)

    class Meta:
        model = Shortcut
        fields = ("uuid", "name", "text", "modified_on")


class OrgReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Org
        fields = ("id", "name")


class TemplateReadSerializer(serializers.ModelSerializer):
    STATUSES = {
        TemplateTranslation.STATUS_PENDING: "pending",
        TemplateTranslation.STATUS_APPROVED: "approved",
        TemplateTranslation.STATUS_REJECTED: "rejected",
        TemplateTranslation.STATUS_PAUSED: "paused",
        TemplateTranslation.STATUS_DISABLED: "disabled",
        TemplateTranslation.STATUS_IN_APPEAL: "in_appeal",
    }

    base_translation = serializers.SerializerMethodField()
    modified_on = serializers.DateTimeField(default_timezone=tzone.utc)
    created_on = serializers.DateTimeField(default_timezone=tzone.utc)

    def get_base_translation(self, obj):
        return self._translation(obj.base_translation) if obj.base_translation else None

    def _translation(self, trans):
        return {
            "channel": {"uuid": str(trans.channel.uuid), "name": trans.channel.name},
            "namespace": trans.namespace,
            "locale": trans.locale,
            "status": self.STATUSES[trans.status],
            "components": trans.components,
            "variables": trans.variables,
            "supported": trans.is_supported,
            "compatible": trans.is_compatible,
        }

    class Meta:
        model = Template
        fields = ("uuid", "name", "base_translation", "created_on", "modified_on")
